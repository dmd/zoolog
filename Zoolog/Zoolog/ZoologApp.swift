import SwiftUI

@main
struct ZoologApp: App {
    @StateObject private var store = PostStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 900, minHeight: 600)
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1200, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("Navigation") {
                Button("Previous Post") { store.selectPrevious() }
                    .keyboardShortcut("k", modifiers: [])
                Button("Next Post") { store.selectNext() }
                    .keyboardShortcut("j", modifiers: [])
                Divider()
                Button("Focus Search") { store.focusSearch = true }
                    .keyboardShortcut("/", modifiers: [])
            }
            CommandMenu("View") {
                Button("Increase Font Size") { store.fontSize = min(store.fontSize + 2, 30) }
                    .keyboardShortcut("=", modifiers: .command)
                Button("Decrease Font Size") { store.fontSize = max(store.fontSize - 2, 10) }
                    .keyboardShortcut("-", modifiers: .command)
                Button("Reset Font Size") { store.fontSize = 15 }
                    .keyboardShortcut("0", modifiers: .command)
            }
        }
    }
}
