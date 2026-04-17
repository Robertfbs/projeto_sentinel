// Funcao utilitaria para remover prefixos hierarquicos separados por ::
(value as nullable text) as nullable text =>
let
    cleaned = if value = null then null else Text.Trim(value),
    result =
        if cleaned = null or cleaned = "" then
            cleaned
        else if Text.Contains(cleaned, "::") then
            Text.Trim(List.Last(Text.Split(cleaned, "::")))
        else
            cleaned
in
    result
