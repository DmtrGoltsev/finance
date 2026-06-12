import Foundation

enum DateHelpers {
    static let displayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateStyle = .long
        f.timeStyle = .none
        return f
    }()

    static let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    static let dateOnlyFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    static let monthFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "LLLL yyyy"
        return f
    }()

    static func todayDateOnly() -> String {
        dateOnlyFormatter.string(from: Date())
    }

    static func nowISO() -> String {
        isoFormatter.string(from: Date())
    }

    static func displayDate(_ dateString: String) -> String {
        if let date = dateOnlyFormatter.date(from: dateString) {
            return displayFormatter.string(from: date)
        }
        if let date = isoFormatter.date(from: dateString) {
            return displayFormatter.string(from: date)
        }
        return dateString
    }

    static func displayMonth(_ yearMonth: String) -> String {
        let parts = yearMonth.split(separator: "-")
        guard parts.count == 2,
              let year = Int(parts[0]),
              let month = Int(parts[1]) else { return yearMonth }
        var comps = DateComponents()
        comps.year = year
        comps.month = month
        guard let date = Calendar.current.date(from: comps) else { return yearMonth }
        return monthFormatter.string(from: date).capitalized
    }

    static func monthStartDate(_ yearMonth: String) -> String {
        "\(yearMonth)-01"
    }

    static func monthEndDate(_ yearMonth: String) -> String {
        let parts = yearMonth.split(separator: "-")
        guard parts.count == 2,
              let year = Int(parts[0]),
              let month = Int(parts[1]) else { return "\(yearMonth)-28" }
        var comps = DateComponents()
        comps.year = year
        comps.month = month + 1
        comps.day = 0
        guard let date = Calendar.current.date(from: comps) else { return "\(yearMonth)-28" }
        return dateOnlyFormatter.string(from: date)
    }

    static func currentYearMonth() -> String {
        let now = Date()
        let cal = Calendar.current
        let year = cal.component(.year, from: now)
        let month = cal.component(.month, from: now)
        return String(format: "%04d-%02d", year, month)
    }
}
