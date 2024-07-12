import os

def mkdir(path):
    try:
        os.makedirs(path)
    except FileExistsError:
        pass
    except Exception as e:
        # sys.stderr.write(traceback.format_exception(*sys.exc_info()))
        raise