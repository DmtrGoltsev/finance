import SwiftUI

struct DatePickerField: View {
    let label: String
    @Binding var date: String
    @State private var showPicker = false
    @State private var pickerDate = Date()

    var body: some View {
        Button {
            if let parsed = DateHelpers.dateOnlyFormatter.date(from: date) {
                pickerDate = parsed
            } else {
                pickerDate = Date()
            }
            showPicker = true
        } label: {
            HStack {
                Text("\(label): \(displayValue)")
                    .font(.subheadline)
                Spacer()
                Image(systemName: "calendar")
                    .foregroundColor(FinanceColors.primary)
            }
            .padding(10)
            .background(FinanceColors.surface)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(FinanceColors.primary.opacity(0.3), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showPicker) {
            NavigationStack {
                DatePicker("", selection: $pickerDate, displayedComponents: .date)
                    .datePickerStyle(.graphical)
                    .padding()
                    .navigationTitle(label)
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) {
                            Button("OK") {
                                date = DateHelpers.dateOnlyFormatter.string(from: pickerDate)
                                showPicker = false
                            }
                        }
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Отмена") {
                                showPicker = false
                            }
                        }
                    }
            }
            .presentationDetents([.medium])
        }
    }

    private var displayValue: String {
        DateHelpers.displayDate(date)
    }
}
