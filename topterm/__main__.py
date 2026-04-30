import sys

from topterm.app import TopTermApp


def main() -> int:
    return TopTermApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
