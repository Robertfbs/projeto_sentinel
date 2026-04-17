let
    DatasBase =
        List.RemoveNulls(
            List.Combine(
                {
                    try fTicketsSolicitacao[data_entrada] otherwise {},
                    try fTicketsSolicitacao[data_resolucao] otherwise {},
                    try fAudiencias[data_audiencia] otherwise {}
                }
            )
        ),
    MinDataEntrada =
        if List.Count(DatasBase) = 0 then Date.From(DateTime.LocalNow()) else Date.From(List.Min(DatasBase)),
    MaxDataResolucao =
        if List.Count(DatasBase) = 0 then Date.From(DateTime.LocalNow()) else Date.From(List.Max(DatasBase)),
    StartDate = #date(Date.Year(MinDataEntrada), 1, 1),
    EndDate = #date(Date.Year(MaxDataResolucao), 12, 31),
    DayCount = Duration.Days(EndDate - StartDate) + 1,
    Dates = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
    TableFromList = Table.FromList(Dates, Splitter.SplitByNothing(), {"Data"}),
    ChangedType = Table.TransformColumnTypes(TableFromList, {{"Data", type date}}),
    AddAno = Table.AddColumn(ChangedType, "Ano", each Date.Year([Data]), Int64.Type),
    AddMesNumero = Table.AddColumn(AddAno, "MesNumero", each Date.Month([Data]), Int64.Type),
    AddMes = Table.AddColumn(AddMesNumero, "Mes", each Date.MonthName([Data], "pt-BR"), type text),
    AddAnoMes = Table.AddColumn(AddMes, "AnoMes", each Date.ToText([Data], "yyyy-MM"), type text),
    AddTrimestre = Table.AddColumn(AddAnoMes, "Trimestre", each "T" & Text.From(Date.QuarterOfYear([Data])), type text),
    AddSemanaAno = Table.AddColumn(AddTrimestre, "SemanaAno", each Date.ToText(Date.StartOfWeek([Data], Day.Monday), "yyyy-MM-dd"), type text),
    AddDia = Table.AddColumn(AddSemanaAno, "Dia", each Date.Day([Data]), Int64.Type),
    AddDiaSemanaNumero = Table.AddColumn(AddDia, "DiaSemanaNumero", each Date.DayOfWeek([Data], Day.Monday) + 1, Int64.Type),
    AddDiaSemana = Table.AddColumn(AddDiaSemanaNumero, "DiaSemana", each Date.DayOfWeekName([Data], "pt-BR"), type text),
    AddFimSemana = Table.AddColumn(AddDiaSemana, "FimDeSemana", each if [DiaSemanaNumero] >= 6 then 1 else 0, Int64.Type)
in
    AddFimSemana
