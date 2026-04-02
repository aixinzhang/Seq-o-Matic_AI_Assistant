"""Status display panel for the Seq-o-Matic GUI.

Handles canvas clearing, note saving, and AWS upload UI toggling.
"""

import os

from front_end.logwindow import add_highlight_mainwindow, widge_attr


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


class StatusPanel:
    """Manages status display elements: canvas clearing, notes, and AWS upload controls.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def clear_focus_canvas(self):
        """Clear the focus canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_focus.draw()

    def clear_align_canvas(self):
        """Clear the alignment canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_align.draw()

    def clear_tile_canvas(self):
        """Clear the tile canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_tile.draw()

    def save_to_note(self):
        """Append the notes text widget content to experiment_detail.txt locally and attempt to upload it to the server."""
        if not os.path.exists(os.path.join(self.app.pos_path, "experiment_detail.txt")):
            open(os.path.join(self.app.pos_path, "experiment_detail.txt"), 'a').close()
        txt = _get_time() + self.app.note_stw.get("1.0", "end-1c") + "\n"
        f = open(os.path.join(self.app.pos_path, "experiment_detail.txt"), "a")
        f.write(txt)
        f.close()
        server_path = '/mnt/imagestorage/' + self.app.pos_path[3:]
        self.app.linux_server = self.app.server
        try:
            cmd = ("scp " + os.path.join(self.app.pos_path, "experiment_detail.txt")
                   + " " + self.app.linux_server + ":" + server_path)
            os.system(cmd)
            txt = _get_time() + "local note saved to experiment_detail.txt, and uploaded to server!" + "\n"
            add_highlight_mainwindow(txt)
        except OSError as e:
            txt = _get_time() + "local note saved to experiment_detail.txt, upload to server is failed!"
            add_highlight_mainwindow(txt)

    def upload_aws(self):
        """Toggle the AWS upload credential fields between editable and disabled."""
        if self.app.upload_aws_value.get() == 1:
            self.app.aws_account_lb.config(fg=widge_attr.normal_color)
            self.app.aws_password_lb.config(fg=widge_attr.normal_color)
            self.app.aws_account_field["state"] = "normal"
            self.app.aws_pwd_field["state"] = "normal"
        else:
            self.app.aws_account_lb.config(fg=widge_attr.disable_color)
            self.app.aws_password_lb.config(fg=widge_attr.disable_color)
            self.app.aws_account_field["state"] = "disable"
            self.app.aws_pwd_field["state"] = "disable"

    def upload_aws_handler(self):
        """Placeholder for future AWS upload functionality."""
        pass
