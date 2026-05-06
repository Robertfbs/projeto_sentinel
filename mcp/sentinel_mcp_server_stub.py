from __future__ import annotations

import json

from sentinel_mcp_manifest import build_manifest


def main() -> None:
    """
    Bootstrap mínimo para inspeção do manifesto MCP do Sentinel.

    Este arquivo não substitui uma implementação completa de servidor MCP.
    Ele existe para materializar, em Python, a estrutura canônica de
    contextos, ferramentas e agentes do projeto sem introduzir novas
    dependências fora do stack atual.
    """

    print(json.dumps(build_manifest(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
