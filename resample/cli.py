import argparse
import resample as m


def main():
    ap = argparse.ArgumentParser(description="采样率转换与延迟补偿")
        ap.add_argument("--to", type=int, required=True)
        ap.add_argument("--out", required=True)
    a = ap.parse_args()
        print("TODO")


if __name__ == "__main__":
    main()
