import sys

from qterm.app import QTermApp


def main() -> int:
    return QTermApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
