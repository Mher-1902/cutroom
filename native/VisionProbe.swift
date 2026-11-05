import Foundation
import Vision
import ImageIO

struct ProbeInput: Decodable { let paths: [String] }
struct TextRegion: Encodable { let rect: [Double]; let text: String; let confidence: Float }
struct ProbeResult: Encodable { let path: String; let faces: [[Double]]; let texts: [TextRegion]; let error: String? }
func normalized(_ box: CGRect) -> [Double] {
    [Double(box.minX), Double(1 - box.maxY), Double(box.width), Double(box.height)]
}
do {
    let bytes = CommandLine.arguments.count > 1 ? try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])) : FileHandle.standardInput.readDataToEndOfFile()
    let input = try JSONDecoder().decode(ProbeInput.self, from: bytes)
    var results: [ProbeResult] = []
    for path in input.paths.prefix(180) {
        autoreleasepool {
            do {
                let faces = VNDetectFaceRectanglesRequest()
                let text = VNRecognizeTextRequest()
                text.recognitionLevel = .accurate
                text.automaticallyDetectsLanguage = true
                text.usesLanguageCorrection = false
                text.minimumTextHeight = 0.025
                let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:])
                try handler.perform([faces, text])
                let regions = (text.results ?? []).compactMap { item -> TextRegion? in
                    guard let candidate = item.topCandidates(1).first, candidate.confidence > 0.25 else { return nil }
                    return TextRegion(rect: normalized(item.boundingBox), text: candidate.string, confidence: candidate.confidence)
                }
                results.append(ProbeResult(path: path, faces: (faces.results ?? []).map { normalized($0.boundingBox) }, texts: regions, error: nil))
            } catch {
                results.append(ProbeResult(path: path, faces: [], texts: [], error: String(describing: error)))
            }
        }
    }
    FileHandle.standardOutput.write(try JSONEncoder().encode(results))
} catch {
    FileHandle.standardError.write(Data(String(describing: error).utf8))
    exit(1)
}
