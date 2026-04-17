let
    Base = Table.SelectColumns(fTicketsSolicitacao, {"assunto"}),
    DistinctRows = Table.Distinct(Base),
    AddAssuntoNormalizado = Table.AddColumn(DistinctRows, "assunto_normalizado", each fxNormalizeHierarchy([assunto]), type text),
    Rename = Table.RenameColumns(AddAssuntoNormalizado, {{"assunto", "assunto_original"}}),
    Reorder = Table.ReorderColumns(Rename, {"assunto_original", "assunto_normalizado"})
in
    Reorder
