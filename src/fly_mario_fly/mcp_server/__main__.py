"""python -m fly_mario_fly.mcp_server   (stdio; see docs for connecting it to Claude and other MCP clients)"""
from fly_mario_fly.mcp_server.server import build_server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
