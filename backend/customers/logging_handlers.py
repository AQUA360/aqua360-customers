import logging
import os
import uuid
import datetime

class PerPostFileHandler(logging.Handler):
    """
    Logging handler that writes each record to its own file:
    logs/<YEARMONTH>/<YYYYMMDD-HHMMSSmmm>-<8hex>.log
    """

    def __init__(self, log_dir=None, **kwargs):
        super().__init__()
        self.base_log_dir = log_dir or os.path.join(os.getcwd(), "logs")
        
        os.makedirs(self.base_log_dir, exist_ok=True)

    def emit(self, record):
        try:
            formatted = self.format(record)

            now = datetime.datetime.now()
            dir_name = now.strftime("%Y%m")                # YEARMONTH (e.g. "202510")
            subdir = os.path.join(self.base_log_dir, dir_name)
            os.makedirs(subdir, exist_ok=True)

            # timestamp with milliseconds
            ts = now.strftime("%Y%m%d-%H%M%S%f")[:-3]  
            uniq = uuid.uuid4().hex[:8]                   
            filename = f"{ts}-{uniq}.log"

            path = os.path.join(subdir, filename)
            # append the single log message (each record => new file)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(formatted)
                fh.write("\n")
        except Exception:
            self.handleError(record)