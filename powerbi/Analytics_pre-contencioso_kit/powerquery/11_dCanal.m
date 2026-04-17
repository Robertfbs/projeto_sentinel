let
    Base = Table.SelectColumns(fTicketsSolicitacao, {"tipo_solicitacao"}),
    DistinctRows = Table.Distinct(Base),
    AddCanalNormalizado = Table.AddColumn(DistinctRows, "canal_normalizado", each fxNormalizeHierarchy([tipo_solicitacao]), type text),
    Rename = Table.RenameColumns(AddCanalNormalizado, {{"tipo_solicitacao", "canal_original"}}),
    Reorder = Table.ReorderColumns(Rename, {"canal_original", "canal_normalizado"})
in
    Reorder
