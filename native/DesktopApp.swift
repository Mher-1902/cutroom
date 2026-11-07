import AppKit
import WebKit

final class DesktopApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var loading: NSView!
    let studio = URL(string: "http://127.0.0.1:8765/")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1220, height: 850), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Cutroom"
        window.minSize = NSSize(width: 540, height: 620)
        window.center()
        window.isReleasedWhenClosed = false
        web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView!.addSubview(web)
        let label = NSTextField(labelWithString: "Opening your local Cutroom studio…")
        label.font = .systemFont(ofSize: 17)
        let spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.startAnimation(nil)
        let stack = NSStackView(views: [spinner, label])
        stack.orientation = .vertical
        stack.spacing = 20
        loading = stack
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([stack.centerXAnchor.constraint(equalTo: window.contentView!.centerXAnchor), stack.centerYAnchor.constraint(equalTo: window.contentView!.centerYAnchor)])
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startStudio()
    }

    func startStudio() {
        guard let root = Bundle.main.object(forInfoDictionaryKey: "CutroomProjectRoot") as? String,
              FileManager.default.isExecutableFile(atPath: root + "/cutroom.command") else {
            showError("The Cutroom project folder has moved. Rebuild the desktop app from its new location using Build Desktop.command.")
            return
        }
        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: root + "/cutroom.command")
            task.arguments = ["start", "--no-browser"]
            task.currentDirectoryURL = URL(fileURLWithPath: root)
            let output = Pipe()
            task.standardOutput = output
            task.standardError = output
            do {
                try task.run()
                let result = output.fileHandleForReading.readDataToEndOfFile()
                task.waitUntilExit()
                DispatchQueue.main.async {
                    if task.terminationStatus == 0 {
                        self.loading.isHidden = true
                        self.web.load(URLRequest(url: self.studio))
                    } else {
                        self.showError(String(data: result, encoding: .utf8) ?? "The local studio could not start.")
                    }
                }
            } catch {
                DispatchQueue.main.async { self.showError(error.localizedDescription) }
            }
        }
    }

    func showError(_ text: String) {
        loading?.isHidden = true
        let alert = NSAlert()
        alert.messageText = "Cutroom could not open"
        alert.informativeText = text
        alert.addButton(withTitle: "Retry")
        alert.addButton(withTitle: "Close")
        alert.beginSheetModal(for: window) { response in
            if response == .alertFirstButtonReturn { self.loading.isHidden = false; self.startStudio() }
            else { NSApp.terminate(nil) }
        }
    }

    func makeMenu() {
        let bar = NSMenu()
        let appItem = NSMenuItem()
        bar.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Open in Browser", action: #selector(openBrowser), keyEquivalent: "b").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Cutroom", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem()
        bar.addItem(editItem)
        editItem.submenu = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            editItem.submenu!.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        let viewItem = NSMenuItem()
        bar.addItem(viewItem)
        viewItem.submenu = NSMenu(title: "View")
        viewItem.submenu!.addItem(withTitle: "Reload", action: #selector(reload), keyEquivalent: "r").target = self
        viewItem.submenu!.addItem(withTitle: "Back", action: #selector(back), keyEquivalent: "[").target = self
        NSApp.mainMenu = bar
    }
    @objc func openBrowser() { NSWorkspace.shared.open(studio) }
    @objc func reload() { web.reload() }
    @objc func back() { if web.canGoBack { web.goBack() } }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func local(_ url: URL) -> Bool {
        url.scheme == "http" && ["127.0.0.1", "localhost"].contains(url.host ?? "") && url.port == 8765 && url.user == nil && url.password == nil
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if local(url) { decisionHandler(.allow) }
        else {
            if ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, ["http", "https"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let attachment = (navigationResponse.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?.lowercased().contains("attachment") ?? false
        decisionHandler(attachment || !navigationResponse.canShowMIMEType ? .download : .allow)
    }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = URL(fileURLWithPath: suggestedFilename).lastPathComponent
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.url : nil) }
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }
}
let application = NSApplication.shared
let delegate = DesktopApp()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
