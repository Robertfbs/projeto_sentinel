let
    Base = Table.SelectColumns(fTicketsSolicitacao, {"status"}),
    DistinctRows = Table.Distinct(Base),
    AddStatusGrupo = Table.AddColumn(
        DistinctRows,
        "status_grupo",
        each
            let s = Text.Upper(Text.Trim(Text.From([status])))
            in
                if List.Contains({"SOLVED", "CLOSED", "RESOLVIDO", "FECHADO"}, s) then "Fechado"
                else if List.Contains({"OPEN", "NEW", "HOLD", "PENDING", "ABERTO"}, s) then "Aberto"
                else "Outros",
        type text
    )
in
    AddStatusGrupo
