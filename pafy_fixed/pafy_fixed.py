from pafy import *

Pafy = None

def new(url, basic=True, gdata=False, size=False,
        callback=None, ydl_opts=None):
    """
    Modified version of pafy.new()
    """
    global Pafy
    if Pafy is None:
        if backend == "internal":
           from pafy.backend_internal import InternPafy as Pafy
        else:
            # changed this line
           from pafy_fixed.backend_youtube_dl_fixed import YtdlPafyFixed as Pafy

    return Pafy(url, basic, gdata, size, callback, ydl_opts=ydl_opts)
