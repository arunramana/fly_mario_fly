"""python -m fly_mario.api [--port 8000]   serve on localhost;   python -m fly_mario.api --export   rewrite openapi.json"""
import argparse


def main() -> None:
    ap = argparse.ArgumentParser(prog="fly_mario.api")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--export", action="store_true", help="write openapi.json and exit")
    args = ap.parse_args()
    from fly_mario.api.app import create_app, export_openapi
    if args.export:
        print(export_openapi())
        return
    import uvicorn
    from fly_mario.api import icons
    icons.ensure_generating()               # object pictures are made in their own process, never on a request
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
