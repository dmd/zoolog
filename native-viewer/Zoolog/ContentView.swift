import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        Group {
            if !store.hasIndexed {
                WelcomeView()
            } else {
                MainView()
            }
        }
        .overlay {
            if store.showLightbox {
                LightboxView()
            }
        }
    }
}

// MARK: - Welcome / Indexing

struct WelcomeView: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        VStack(spacing: 24) {
            if store.isIndexing {
                VStack(spacing: 16) {
                    ProgressView()
                        .scaleEffect(1.5)
                    Text(store.indexingProgress)
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
            } else {
                Image(systemName: "book.pages")
                    .font(.system(size: 64))
                    .foregroundStyle(.teal)

                Text("Zoolog")
                    .font(.largeTitle.weight(.bold))
                    .foregroundStyle(.primary)

                Text("Family Journal Browser")
                    .font(.title3)
                    .foregroundStyle(.secondary)

                ProgressView()
                Text(store.indexingProgress)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.background)
    }
}

// MARK: - Main Layout

struct MainView: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        VStack(spacing: 0) {
            FilterBar()
            HSplitView {
                PostListPanel()
                    .frame(minWidth: 280, idealWidth: 350)
                PostDetailPanel()
                    .frame(minWidth: 400)
            }
            StatusBar()
        }
    }
}

// MARK: - Filter Bar

struct FilterBar: View {
    @EnvironmentObject var store: PostStore
    @FocusState private var searchFocused: Bool

    var body: some View {
        HStack(spacing: 12) {
            // Search
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary)
                TextField("Search entries...", text: $store.searchText)
                    .textFieldStyle(.plain)
                    .focused($searchFocused)
                if !store.searchText.isEmpty {
                    Button(action: { store.searchText = "" }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(8)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
            .frame(maxWidth: 300)

            // Category
            Picker("Category", selection: $store.selectedCategory) {
                ForEach(Category.allCases) { cat in
                    Text(cat.label).tag(cat)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 350)
            .onChange(of: store.selectedCategory) { store.applyFilters() }

            Spacer()

            // Date range
            DatePicker("From", selection: $store.startDate, displayedComponents: .date)
                .labelsHidden()
                .frame(width: 110)
                .onChange(of: store.startDate) { store.applyFilters() }

            Text("to")
                .foregroundStyle(.secondary)

            DatePicker("To", selection: $store.endDate, displayedComponents: .date)
                .labelsHidden()
                .frame(width: 110)
                .onChange(of: store.endDate) { store.applyFilters() }

            Button(action: { resetFilters() }) {
                Image(systemName: "arrow.counterclockwise")
            }
            .buttonStyle(.bordered)
            .help("Reset filters")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
        .onChange(of: store.focusSearch) {
            if store.focusSearch {
                searchFocused = true
                store.focusSearch = false
            }
        }
    }

    private func resetFilters() {
        store.searchText = ""
        store.selectedCategory = .all
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        if let d = fmt.date(from: String(store.stats.minDate.prefix(10))) { store.startDate = d }
        if let d = fmt.date(from: String(store.stats.maxDate.prefix(10))) { store.endDate = d }
        store.applyFilters()
    }
}

// MARK: - Post List

struct PostListPanel: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Entries")
                    .font(.headline)
                Spacer()
                Text("\(store.posts.count) of \(store.totalPosts)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)

            Divider()

            if store.isLoading && store.posts.isEmpty {
                Spacer()
                ProgressView("Loading...")
                Spacer()
            } else if store.posts.isEmpty {
                Spacer()
                VStack(spacing: 8) {
                    Image(systemName: "doc.text.magnifyingglass")
                        .font(.largeTitle)
                        .foregroundStyle(.tertiary)
                    Text("No entries found")
                        .foregroundStyle(.secondary)
                }
                Spacer()
            } else {
                ScrollViewReader { proxy in
                    List(store.posts, selection: Binding(
                        get: { store.selectedPost },
                        set: { post in
                            if let post { store.selectPost(post) }
                        }
                    )) { post in
                        PostRow(post: post, isSelected: store.selectedPost == post, searchText: store.searchText)
                            .tag(post)
                            .id(post.id)
                            .onAppear {
                                if post == store.posts.last {
                                    Task { await store.loadMorePosts() }
                                }
                            }
                    }
                    .listStyle(.inset)
                    .onChange(of: store.selectedPost) {
                        if let post = store.selectedPost {
                            withAnimation {
                                proxy.scrollTo(post.id, anchor: .center)
                            }
                        }
                    }
                }
            }
        }
        .background(.background)
    }
}

struct PostRow: View {
    @EnvironmentObject var store: PostStore
    let post: Post
    let isSelected: Bool
    let searchText: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Text(post.displayDate)
                    .font(.system(size: store.fontSize - 2, design: .monospaced))
                    .foregroundStyle(.secondary)

                CategoryBadge(category: post.category)

                Spacer()
            }

            Text(post.excerpt)
                .font(.system(size: store.fontSize - 2, design: .serif))
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

struct CategoryBadge: View {
    let category: String

    var body: some View {
        Text(category)
            .font(.system(size: 10, weight: .semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(category.categoryColor.opacity(0.15), in: Capsule())
            .foregroundStyle(category.categoryColor)
    }
}

// MARK: - Post Detail

struct PostDetailPanel: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        VStack(spacing: 0) {
            if let post = store.selectedPost {
                // Navigation bar
                HStack {
                    Button(action: { store.selectPrevious() }) {
                        Label("Previous", systemImage: "chevron.left")
                    }
                    .disabled(store.posts.first == store.selectedPost)
                    .keyboardShortcut(.leftArrow, modifiers: [])

                    Spacer()

                    Text(post.displayDate)
                        .font(.headline)

                    CategoryBadge(category: post.category)

                    Spacer()

                    Button(action: { store.selectNext() }) {
                        Label("Next", systemImage: "chevron.right")
                    }
                    .disabled(store.posts.last == store.selectedPost)
                    .keyboardShortcut(.rightArrow, modifiers: [])
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)

                Divider()

                // Content
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(post.filename)
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                            .padding(.bottom, 8)

                        PostContentView(content: post.content, searchTerms: searchTerms)
                    }
                    .padding(24)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Photo shelf
                PhotoShelf()
            } else {
                VStack(spacing: 16) {
                    Image(systemName: "text.document")
                        .font(.system(size: 48))
                        .foregroundStyle(.tertiary)
                    Text("Select an entry to read")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                    Text("Use j/k or arrow keys to navigate")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(.background)
    }

    private var searchTerms: [String] {
        let text = store.searchText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return [] }
        return text.split(separator: " ").map(String.init)
    }
}

struct PostContentView: View {
    @EnvironmentObject var store: PostStore
    let content: String
    let searchTerms: [String]

    private var paragraphs: [String] {
        content.components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: store.fontSize) {
            ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, para in
                if searchTerms.isEmpty {
                    Text(LocalizedStringKey(para))
                        .font(.system(size: store.fontSize, design: .serif))
                        .lineSpacing(4)
                        .textSelection(.enabled)
                } else {
                    highlightedText(for: para)
                        .font(.system(size: store.fontSize, design: .serif))
                        .lineSpacing(4)
                        .textSelection(.enabled)
                }
            }
        }
    }

    private func highlightedText(for text: String) -> Text {
        var attr = AttributedString(text)
        let lower = text.lowercased()

        for term in searchTerms {
            let termLower = term.lowercased()
            var searchStart = lower.startIndex
            while let range = lower.range(of: termLower, range: searchStart..<lower.endIndex) {
                let attrRange = attr.index(attr.startIndex, offsetByCharacters: text.distance(from: text.startIndex, to: range.lowerBound)) ..<
                    attr.index(attr.startIndex, offsetByCharacters: text.distance(from: text.startIndex, to: range.upperBound))
                attr[attrRange].backgroundColor = .yellow.opacity(0.4)
                attr[attrRange].inlinePresentationIntent = .stronglyEmphasized
                searchStart = range.upperBound
            }
        }

        return Text(attr)
    }
}

// MARK: - Photo Shelf

struct PhotoShelf: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        VStack(spacing: 0) {
            Divider()

            ZStack {
                if store.photos.isEmpty {
                    HStack(spacing: 6) {
                        Image(systemName: "photo")
                            .foregroundStyle(.quaternary)
                        Text("No photos")
                            .font(.caption)
                            .foregroundStyle(.quaternary)
                    }
                } else {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(Array(store.photos.enumerated()), id: \.offset) { index, image in
                                Image(nsImage: image)
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 135, height: 135)
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                                    .contentShape(Rectangle())
                                    .onTapGesture { store.openLightbox(at: index) }
                            }
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                    }
                }
            }
            .frame(height: 151)
            .frame(maxWidth: .infinity)
        }
        .background(.bar)
    }
}

// MARK: - Lightbox

struct LightboxView: View {
    @EnvironmentObject var store: PostStore
    @FocusState private var lightboxFocused: Bool

    var body: some View {
        ZStack {
            Color.black.opacity(0.85)
                .ignoresSafeArea()
                .onTapGesture { store.closeLightbox() }

            if let idx = store.selectedPhotoIndex, idx < store.photos.count {
                Image(nsImage: store.photos[idx])
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(40)
            }

            // Navigation
            HStack {
                Button(action: { store.previousPhoto() }) {
                    Image(systemName: "chevron.left.circle.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(.white.opacity(0.8))
                }
                .buttonStyle(.plain)
                .disabled(store.selectedPhotoIndex == 0)
                .opacity((store.selectedPhotoIndex ?? 0) == 0 ? 0.3 : 1)

                Spacer()

                Button(action: { store.nextPhoto() }) {
                    Image(systemName: "chevron.right.circle.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(.white.opacity(0.8))
                }
                .buttonStyle(.plain)
                .disabled(store.selectedPhotoIndex == store.photos.count - 1)
                .opacity((store.selectedPhotoIndex ?? 0) == store.photos.count - 1 ? 0.3 : 1)
            }
            .padding(.horizontal, 20)

            // Close button
            VStack {
                HStack {
                    Spacer()
                    Button(action: { store.closeLightbox() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 30))
                            .foregroundStyle(.white.opacity(0.8))
                    }
                    .buttonStyle(.plain)
                    .padding(20)
                }
                Spacer()
            }

            // Counter
            VStack {
                Spacer()
                if let idx = store.selectedPhotoIndex {
                    Text("\(idx + 1) / \(store.photos.count)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.6))
                        .padding(.bottom, 20)
                }
            }
        }
        .focusable()
        .focused($lightboxFocused)
        .onExitCommand { store.closeLightbox() }
        .onAppear { lightboxFocused = true }
    }
}

// MARK: - Status Bar

struct StatusBar: View {
    @EnvironmentObject var store: PostStore

    var body: some View {
        HStack(spacing: 16) {
            Text("Total: \(store.stats.total) entries")
                .font(.caption)

            Spacer()

            ForEach(["A", "D", "J", "AHNS"], id: \.self) { (cat: String) in
                if let count = store.stats.categories[cat] {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(cat.categoryColor)
                            .frame(width: 6, height: 6)
                        Text("\(cat): \(count)")
                            .font(.caption)
                    }
                }
            }

            Spacer()

            if !store.stats.minDate.isEmpty {
                Text("\(String(store.stats.minDate.prefix(10))) .. \(String(store.stats.maxDate.prefix(10)))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .background(.bar)
    }
}
