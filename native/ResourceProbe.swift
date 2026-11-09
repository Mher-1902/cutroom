import Foundation

let state = ProcessInfo.processInfo.thermalState
let names = ["nominal", "fair", "serious", "critical"]
let value = state.rawValue
let result: [String: Any] = ["thermal_state": value, "thermal_name": value >= 0 && value < names.count ? names[value] : "unknown"]
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
