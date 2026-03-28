import Foundation
import SQLite3

/// Lightweight SQLite wrapper for the Zoolog posts database.
final class Database {
    private var db: OpaquePointer?

    init() {
        openInMemory()
        createSchema()
    }

    deinit {
        sqlite3_close(db)
    }

    // MARK: - Setup

    private func openInMemory() {
        guard sqlite3_open(":memory:", &db) == SQLITE_OK else {
            fatalError("Failed to open in-memory database")
        }
    }

    private func createSchema() {
        exec("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT,
            content TEXT,
            clean_title TEXT,
            clean_content TEXT,
            excerpt TEXT,
            year INTEGER,
            month INTEGER,
            day INTEGER
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            filename, clean_title, clean_content, category,
            content='posts', content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
            INSERT INTO posts_fts(rowid, filename, clean_title, clean_content, category)
            VALUES (new.id, new.filename, new.clean_title, new.clean_content, new.category);
        END;
        CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date);
        CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
        CREATE INDEX IF NOT EXISTS idx_posts_year_month ON posts(year, month);
        """)
    }

    // MARK: - Indexing

    func indexPosts(from directory: URL, progress: @escaping (Int, Int) -> Void) -> Int {
        exec("DELETE FROM posts")

        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            .filter({ $0.pathExtension == "txt" })
            .sorted(by: { $0.lastPathComponent < $1.lastPathComponent })
        else { return 0 }

        let total = files.count
        var indexed = 0

        for (i, file) in files.enumerated() {
            guard let content = try? String(contentsOf: file, encoding: .utf8),
                  let info = extractPostInfo(filename: file.lastPathComponent, content: content)
            else { continue }

            insertPost(info)
            indexed += 1
            if indexed % 500 == 0 || i == total - 1 {
                progress(i + 1, total)
            }
        }
        return indexed
    }

    private func insertPost(_ info: PostInfo) {
        let sql = """
        INSERT INTO posts (filename, date, category, title, content, clean_title, clean_content, excerpt, year, month, day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_text(stmt, 1, (info.filename as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 2, (info.dateString as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 3, (info.category as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 4, (info.title as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 5, (info.content as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 6, (info.cleanTitle as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 7, (info.cleanContent as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 8, (info.excerpt as NSString).utf8String, -1, nil)
        sqlite3_bind_int(stmt, 9, Int32(info.year))
        sqlite3_bind_int(stmt, 10, Int32(info.month))
        sqlite3_bind_int(stmt, 11, Int32(info.day))

        sqlite3_step(stmt)
    }

    // MARK: - Queries

    func queryPosts(search: String = "", category: String = "", startDate: String = "", endDate: String = "", limit: Int = 500, offset: Int = 0) -> (posts: [Post], total: Int) {
        var conditions: [String] = []
        var params: [String] = []

        if !category.isEmpty {
            if category == "US" {
                conditions.append("posts.category IN (?, ?)")
                params += ["A", "D"]
            } else {
                conditions.append("posts.category = ?")
                params.append(category)
            }
        }

        if !startDate.isEmpty {
            conditions.append("posts.date >= ?")
            params.append(startDate)
        }

        if !endDate.isEmpty {
            if let d = parseDate(endDate) {
                let next = Calendar.current.date(byAdding: .day, value: 1, to: d)!
                let fmt = DateFormatter()
                fmt.dateFormat = "yyyy-MM-dd"
                conditions.append("posts.date < ?")
                params.append(fmt.string(from: next))
            }
        }

        let sanitized = sanitizeFTS(search)
        var sql: String
        var countSql: String
        var allParams: [String]
        var countParams: [String]

        if !sanitized.isEmpty {
            let wc = conditions.isEmpty ? "" : "AND " + conditions.joined(separator: " AND ")
            sql = """
            SELECT posts.* FROM posts_fts
            JOIN posts ON posts.id = posts_fts.rowid
            WHERE posts_fts MATCH ? \(wc)
            ORDER BY date ASC LIMIT ? OFFSET ?
            """
            countSql = """
            SELECT COUNT(*) FROM posts_fts
            JOIN posts ON posts.id = posts_fts.rowid
            WHERE posts_fts MATCH ? \(wc)
            """
            allParams = [sanitized] + params + ["\(limit)", "\(offset)"]
            countParams = [sanitized] + params
        } else {
            let wc = conditions.isEmpty ? "" : "WHERE " + conditions.joined(separator: " AND ")
            sql = "SELECT * FROM posts \(wc) ORDER BY date ASC LIMIT ? OFFSET ?"
            countSql = "SELECT COUNT(*) FROM posts \(wc)"
            allParams = params + ["\(limit)", "\(offset)"]
            countParams = params
        }

        let posts = executeQuery(sql, params: allParams)
        let total = executeCount(countSql, params: countParams)
        return (posts, total)
    }

    func getPost(id: Int) -> Post? {
        let results = executeQuery("SELECT * FROM posts WHERE id = ?", params: ["\(id)"])
        return results.first
    }

    func getStats() -> PostStats {
        var stats = PostStats()

        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM posts", -1, &stmt, nil) == SQLITE_OK {
            if sqlite3_step(stmt) == SQLITE_ROW {
                stats.total = Int(sqlite3_column_int(stmt, 0))
            }
        }
        sqlite3_finalize(stmt)

        stmt = nil
        if sqlite3_prepare_v2(db, "SELECT category, COUNT(*) FROM posts GROUP BY category", -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                if let cat = sqlite3_column_text(stmt, 0) {
                    let name = String(cString: cat)
                    let count = Int(sqlite3_column_int(stmt, 1))
                    stats.categories[name] = count
                }
            }
        }
        sqlite3_finalize(stmt)

        stmt = nil
        if sqlite3_prepare_v2(db, "SELECT MIN(date), MAX(date) FROM posts", -1, &stmt, nil) == SQLITE_OK {
            if sqlite3_step(stmt) == SQLITE_ROW {
                if let mn = sqlite3_column_text(stmt, 0) { stats.minDate = String(cString: mn) }
                if let mx = sqlite3_column_text(stmt, 1) { stats.maxDate = String(cString: mx) }
            }
        }
        sqlite3_finalize(stmt)

        return stats
    }

    // MARK: - Helpers

    private func exec(_ sql: String) {
        var err: UnsafeMutablePointer<CChar>?
        sqlite3_exec(db, sql, nil, nil, &err)
        if let err = err { sqlite3_free(err) }
    }

    private func executeQuery(_ sql: String, params: [String]) -> [Post] {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
        defer { sqlite3_finalize(stmt) }

        for (i, p) in params.enumerated() {
            sqlite3_bind_text(stmt, Int32(i + 1), (p as NSString).utf8String, -1, nil)
        }

        var results: [Post] = []
        let dateFmt = DateFormatter()
        dateFmt.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let dateFmt2 = DateFormatter()
        dateFmt2.dateFormat = "yyyy-MM-dd"

        while sqlite3_step(stmt) == SQLITE_ROW {
            let id = Int(sqlite3_column_int(stmt, 0))
            let filename = col(stmt, 1)
            let dateStr = col(stmt, 2)
            let category = col(stmt, 3)
            let title = col(stmt, 4)
            let content = col(stmt, 5)
            let excerpt = col(stmt, 8)
            let year = Int(sqlite3_column_int(stmt, 9))
            let month = Int(sqlite3_column_int(stmt, 10))
            let day = Int(sqlite3_column_int(stmt, 11))

            let date = dateFmt.date(from: dateStr)
                ?? dateFmt2.date(from: String(dateStr.prefix(10)))
                ?? Date.distantPast

            results.append(Post(
                id: id, filename: filename, date: date,
                dateString: String(dateStr.prefix(10)),
                category: category, title: title,
                content: content, excerpt: excerpt,
                year: year, month: month, day: day
            ))
        }
        return results
    }

    private func executeCount(_ sql: String, params: [String]) -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return 0 }
        defer { sqlite3_finalize(stmt) }

        for (i, p) in params.enumerated() {
            sqlite3_bind_text(stmt, Int32(i + 1), (p as NSString).utf8String, -1, nil)
        }

        if sqlite3_step(stmt) == SQLITE_ROW {
            return Int(sqlite3_column_int(stmt, 0))
        }
        return 0
    }

    private func col(_ stmt: OpaquePointer?, _ index: Int32) -> String {
        if let text = sqlite3_column_text(stmt, index) {
            return String(cString: text)
        }
        return ""
    }

    private func sanitizeFTS(_ query: String) -> String {
        guard !query.isEmpty else { return "" }
        var s = query
        for ch in ["*", "(", ")", ":", "\"", "-", "'"] {
            s = s.replacingOccurrences(of: ch, with: " ")
        }
        for op in ["AND", "OR", "NOT", "NEAR"] {
            s = s.replacingOccurrences(of: " \(op) ", with: " ")
            s = s.replacingOccurrences(of: " \(op.lowercased()) ", with: " ")
        }
        return s.split(separator: " ").joined(separator: " ")
    }

    private func parseDate(_ str: String) -> Date? {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        return fmt.date(from: str)
    }
}

// MARK: - Post extraction

private struct PostInfo {
    let filename: String
    let dateString: String
    let category: String
    let title: String
    let content: String
    let cleanTitle: String
    let cleanContent: String
    let excerpt: String
    let year: Int
    let month: Int
    let day: Int
}

private func extractPostInfo(filename: String, content: String) -> PostInfo? {
    let parts = filename.replacingOccurrences(of: ".txt", with: "").split(separator: "-")
    guard parts.count >= 6 else { return nil }

    let dateStr = "\(parts[0])-\(parts[1])-\(parts[2])"
    let fmt = DateFormatter()
    fmt.dateFormat = "yyyy-MM-dd"
    guard let dt = fmt.date(from: dateStr) else { return nil }

    var cat = "US"
    if filename.contains("AHNS") { cat = "AHNS" }
    else if filename.contains("J") { cat = "J" }
    else if filename.contains("-D-") { cat = "D" }
    else if filename.contains("-A-") { cat = "A" }

    // Decode quoted-printable
    let decoded = decodeQuotedPrintable(content)

    let lines = decoded.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "\n", omittingEmptySubsequences: false)
    let skip = (!lines.isEmpty && lines[0].hasPrefix("#")) ? 1 : 0
    let body = lines.dropFirst(skip).joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)

    let title: String
    if !body.isEmpty {
        let t = String(body.prefix(50)).replacingOccurrences(of: "\n", with: " ").trimmingCharacters(in: .whitespaces)
        title = body.count > 50 ? t + "..." : t
    } else {
        title = "\(dateStr) \(cat)"
    }

    let excerpt = body.count > 200 ? String(body.prefix(200)) + "..." : body

    let cal = Calendar.current
    let comps = cal.dateComponents([.year, .month, .day], from: dt)

    return PostInfo(
        filename: filename, dateString: dateStr, category: cat,
        title: title, content: body,
        cleanTitle: cleanForSearch(title), cleanContent: cleanForSearch(body),
        excerpt: excerpt,
        year: comps.year!, month: comps.month!, day: comps.day!
    )
}

private func cleanForSearch(_ text: String) -> String {
    guard !text.isEmpty else { return "" }
    let pattern = try! NSRegularExpression(pattern: "[^\\w\\s]", options: [])
    let cleaned = pattern.stringByReplacingMatches(in: text, range: NSRange(text.startIndex..., in: text), withTemplate: " ")
    return cleaned.split(separator: " ").joined(separator: " ")
}

private func decodeQuotedPrintable(_ input: String) -> String {
    var result = ""
    var i = input.startIndex
    while i < input.endIndex {
        let ch = input[i]
        if ch == "=" {
            let next1 = input.index(i, offsetBy: 1, limitedBy: input.endIndex)
            let next2 = input.index(i, offsetBy: 2, limitedBy: input.endIndex)

            if let n1 = next1, let n2 = next2, n2 <= input.endIndex {
                let hex = String(input[n1..<n2])
                if hex == "\r\n" || input[n1] == "\n" {
                    // Soft line break
                    i = input[n1] == "\r" ? n2 : input.index(after: n1)
                    continue
                }
                if let byte = UInt8(hex, radix: 16) {
                    result.append(Character(UnicodeScalar(byte)))
                    i = n2
                    continue
                }
            }
        }
        result.append(ch)
        i = input.index(after: i)
    }
    return result
}
