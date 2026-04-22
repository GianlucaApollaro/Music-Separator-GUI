import wx

EVT_LOG_ID = wx.NewIdRef()
EVT_DONE_ID = wx.NewIdRef()
EVT_PROGRESS_ID = wx.NewIdRef()

class ProgressEvent(wx.PyEvent):
    def __init__(self, value, maximum=100):
        super().__init__()
        self.SetEventType(EVT_PROGRESS_ID)
        self.value = value
        self.maximum = maximum

class LogEvent(wx.PyEvent):
    def __init__(self, message):
        super().__init__()
        self.SetEventType(EVT_LOG_ID)
        self.message = message

class DoneEvent(wx.PyEvent):
    def __init__(self, success, message=""):
        super().__init__()
        self.SetEventType(EVT_DONE_ID)
        self.success = success
        self.message = message
