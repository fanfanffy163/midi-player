import multiprocessing

from midiplayer.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
