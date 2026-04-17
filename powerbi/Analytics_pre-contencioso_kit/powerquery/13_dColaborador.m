let
    Base = Table.SelectColumns(fTicketsSolicitacao, {"atribuido"}),
    DistinctRows = Table.Distinct(Base),
    Rename = Table.RenameColumns(DistinctRows, {{"atribuido", "colaborador"}}),
    Sorted = Table.Sort(Rename, {{"colaborador", Order.Ascending}})
in
    Sorted
