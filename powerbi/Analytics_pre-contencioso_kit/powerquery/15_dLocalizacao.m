let
    Base = Table.SelectColumns(fTicketsSolicitacao, {"municipio", "bairro", "bloco"}),
    DistinctRows = Table.Distinct(Base),
    Sorted = Table.Sort(DistinctRows, {{"municipio", Order.Ascending}, {"bairro", Order.Ascending}})
in
    Sorted
