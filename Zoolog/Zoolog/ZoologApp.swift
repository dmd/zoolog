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
        }
    }
}
