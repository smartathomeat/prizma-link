import Foundation
import IOBluetooth

private func fail(_ message: String, code: Int32) -> Never {
    fputs("\(message)\n", stderr)
    exit(code)
}

private func runLoop(until predicate: () -> Bool, timeout: TimeInterval) {
    let deadline = Date().addingTimeInterval(timeout)
    while !predicate() && Date() < deadline {
        RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    }
}

private final class Finder: NSObject, IOBluetoothDeviceInquiryDelegate {
    let targetName: String
    let targetAddress: String
    var target: IOBluetoothDevice?
    var done = false

    init(targetName: String, targetAddress: String) {
        self.targetName = targetName
        self.targetAddress = targetAddress
    }

    func deviceInquiryDeviceFound(
        _ sender: IOBluetoothDeviceInquiry!,
        device: IOBluetoothDevice!
    ) {
        if matches(device, name: targetName, address: targetAddress) {
            target = device
            done = true
            sender.stop()
        }
    }

    func deviceInquiryComplete(
        _ sender: IOBluetoothDeviceInquiry!,
        error: IOReturn,
        aborted: Bool
    ) {
        done = true
    }
}

private final class Pairer: NSObject, IOBluetoothDevicePairDelegate {
    let pairingPIN: [UInt8]
    var done = false
    var result: IOReturn = kIOReturnError

    init(pin: String) {
        pairingPIN = Array(pin.utf8)
    }

    func devicePairingPINCodeRequest(_ sender: Any!) {
        guard let pair = sender as? IOBluetoothDevicePair else { return }
        var code = BluetoothPINCode()
        withUnsafeMutableBytes(of: &code) { buffer in
            buffer.initializeMemory(as: UInt8.self, repeating: 0)
            buffer.copyBytes(from: pairingPIN)
        }
        pair.replyPINCode(pairingPIN.count, pinCode: &code)
    }

    func devicePairingUserConfirmationRequest(
        _ sender: Any!,
        numericValue: BluetoothNumericValue
    ) {
        (sender as? IOBluetoothDevicePair)?.replyUserConfirmation(true)
    }

    func devicePairingFinished(_ sender: Any!, error: IOReturn) {
        result = error
        done = true
    }
}

private final class SDPWaiter: NSObject {
    var done = false
    var result: IOReturn = kIOReturnError

    @objc func sdpQueryComplete(_ device: IOBluetoothDevice!, status: IOReturn) {
        result = status
        done = true
    }
}

private final class RFCOMMReader: NSObject, IOBluetoothRFCOMMChannelDelegate {
    var received = Data()
    var closed = false

    func rfcommChannelData(
        _ rfcommChannel: IOBluetoothRFCOMMChannel!,
        data dataPointer: UnsafeMutableRawPointer!,
        length dataLength: Int
    ) {
        guard let dataPointer, dataLength > 0 else { return }
        received.append(dataPointer.assumingMemoryBound(to: UInt8.self), count: dataLength)
    }

    func rfcommChannelClosed(_ rfcommChannel: IOBluetoothRFCOMMChannel!) {
        closed = true
    }
}

private func argumentValue(_ flag: String) -> String? {
    guard let index = CommandLine.arguments.firstIndex(of: flag) else { return nil }
    let valueIndex = CommandLine.arguments.index(after: index)
    guard valueIndex < CommandLine.arguments.endIndex else { return nil }
    return CommandLine.arguments[valueIndex]
}

guard let targetName = argumentValue("--name"), targetName.hasPrefix("PSN_IF-") else {
    fail("INVALID_OR_MISSING_NAME", code: 2)
}
guard let addressValue = argumentValue("--address") else {
    fail("INVALID_OR_MISSING_ADDRESS", code: 2)
}
let addressParts = addressValue.uppercased().split(separator: ":", omittingEmptySubsequences: false)
guard addressParts.count == 6,
      addressParts.allSatisfy({ part in
          part.count == 2 && part.allSatisfy({ $0.isHexDigit })
      }) else {
    fail("INVALID_OR_MISSING_ADDRESS", code: 2)
}
private let targetAddress = addressParts.map(String.init).joined(separator: ":")
guard let pinValue = argumentValue("--pin"),
      (1...16).contains(pinValue.count),
      pinValue.allSatisfy({ $0.isNumber && $0.isASCII }) else {
    fail("INVALID_OR_MISSING_PIN", code: 2)
}

private func matches(_ device: IOBluetoothDevice, name: String, address: String) -> Bool {
    device.name == name && device.addressString.uppercased() == address
}

let paired = (IOBluetoothDevice.pairedDevices() as? [IOBluetoothDevice]) ?? []
let pairedMatches = paired.filter({ matches($0, name: targetName, address: targetAddress) })
guard pairedMatches.count <= 1 else {
    fail("AMBIGUOUS_CONFIGURED_DEVICE", code: 3)
}
var device = pairedMatches.first
if device == nil {
    let finder = Finder(targetName: targetName, targetAddress: targetAddress)
    guard let inquiry = IOBluetoothDeviceInquiry(delegate: finder) else {
        fail("INQUIRY_CREATE_FAILED", code: 3)
    }
    inquiry.inquiryLength = 12
    inquiry.updateNewDeviceNames = true
    guard inquiry.start() == kIOReturnSuccess else {
        fail("INQUIRY_START_FAILED", code: 4)
    }
    runLoop(until: { finder.done }, timeout: 22)
    device = finder.target
}
guard let device else {
    fail("PRISM_NOT_FOUND", code: 5)
}
guard matches(device, name: targetName, address: targetAddress) else {
    fail("PRISM_IDENTITY_MISMATCH", code: 5)
}

if !device.isPaired() {
    guard let pairing = IOBluetoothDevicePair(device: device) else {
        fail("PAIR_CREATE_FAILED", code: 6)
    }
    let pairer = Pairer(pin: pinValue)
    pairing.delegate = pairer
    guard pairing.start() == kIOReturnSuccess else {
        fail("PAIR_START_FAILED", code: 7)
    }
    runLoop(until: { pairer.done }, timeout: 35)
    guard pairer.done, pairer.result == kIOReturnSuccess else {
        pairing.stop()
        fail("PAIR_FAILED_OR_TIMEOUT", code: 8)
    }
}

let basebandResult = device.openConnection()
guard basebandResult == kIOReturnSuccess || device.isConnected() else {
    fail("BASEBAND_OPEN_FAILED", code: 9)
}

private let sdp = SDPWaiter()
guard device.performSDPQuery(sdp) == kIOReturnSuccess else {
    fail("SDP_START_FAILED", code: 10)
}
runLoop(until: { sdp.done }, timeout: 25)
guard sdp.done, sdp.result == kIOReturnSuccess else {
    fail("SDP_FAILED_OR_TIMEOUT", code: 11)
}

let serialPortUUID = IOBluetoothSDPUUID.uuid16(0x1101)
guard let service = device.getServiceRecord(for: serialPortUUID) else {
    fail("SPP_NOT_FOUND", code: 12)
}
var channelID: BluetoothRFCOMMChannelID = 0
guard service.getRFCOMMChannelID(&channelID) == kIOReturnSuccess else {
    fail("SPP_CHANNEL_FAILED", code: 13)
}

private let reader = RFCOMMReader()
var channel: IOBluetoothRFCOMMChannel?
let openResult = device.openRFCOMMChannelSync(
    &channel,
    withChannelID: channelID,
    delegate: reader
)
guard openResult == kIOReturnSuccess, let channel else {
    fail("RFCOMM_OPEN_FAILED", code: 14)
}
defer {
    channel.close()
    device.closeConnection()
}

print("READY")
fflush(stdout)

while let command = readLine(strippingNewline: true) {
    guard command == "%ms;" else {
        fputs("BLOCKED_NON_STATUS_COMMAND\n", stderr)
        continue
    }
    reader.received.removeAll(keepingCapacity: true)
    var query = Array(command.utf8)
    let writeResult = query.withUnsafeMutableBytes { buffer -> IOReturn in
        guard let baseAddress = buffer.baseAddress else { return kIOReturnBadArgument }
        return channel.writeSync(baseAddress, length: UInt16(buffer.count))
    }
    guard writeResult == kIOReturnSuccess else {
        fail("STATUS_WRITE_FAILED", code: 15)
    }
    runLoop(
        until: { reader.received.contains(UInt8(ascii: ";")) || reader.closed },
        timeout: 5
    )
    guard let delimiter = reader.received.firstIndex(of: UInt8(ascii: ";")) else {
        fail("STATUS_TIMEOUT", code: 16)
    }
    let frameData = reader.received.prefix(through: delimiter)
    guard let response = String(data: frameData, encoding: .ascii) else {
        fail("STATUS_NON_ASCII", code: 17)
    }
    print(response)
    fflush(stdout)
}
