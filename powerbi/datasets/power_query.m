// Power Query (M) - paste each query into Advanced Editor in Power BI Desktop.
// Parameter: BaseUrl = "http://localhost:8000/api/analytics" (Text parameter).
// Auth: the API requires login. Use Web connector -> Basic credentials (a read-only
// Django user), NOT an admin account. Prefer CSV file import for a first demo.

// --- Query: Loans (fact) ---
let
    Source = Csv.Document(Web.Contents(BaseUrl & "/loans.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"loan_amount", type number}, {"funded_amount", type number}, {"interest_rate", type number},
        {"annual_income", type number}, {"dti", type number}, {"total_payment", type number},
        {"principal_received", type number}, {"interest_received", type number}, {"recoveries", type number},
        {"recovery_fees", type number}, {"outstanding_principal", type number},
        {"issue_date", type date}, {"last_payment_date", type date}, {"term_months", Int64.Type}}, "en-US"),
    // Cleaning: blanks stay null (never imputed here); duplicates already prevented by Django (source, loan_id).
    NoBlankId = Table.SelectRows(Typed, each [loan_id] <> null and [loan_id] <> "")
in
    NoBlankId

// --- Query: Calendar (date dimension) ---
// let
//     Start = Date.StartOfYear(List.Min(Loans[issue_date])),
//     End = Date.EndOfYear(List.Max(Loans[issue_date])),
//     Days = List.Dates(Start, Duration.Days(End - Start) + 1, #duration(1,0,0,0)),
//     T = Table.FromList(Days, Splitter.SplitByNothing(), {"Date"}, null, ExtraValues.Error),
//     Typed = Table.TransformColumnTypes(T, {{"Date", type date}})
// in Typed

// --- Query: Sources (provenance) ---   ... BaseUrl & "/sources/?export=csv"
// --- Query: RBIRules                   ... BaseUrl & "/india-rules/?export=csv"
