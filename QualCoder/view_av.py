# -*- coding: utf-8 -*-

'''
Copyright (c) 2019 Colin Curtain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Author: Colin Curtain (ccbogel)
https://github.com/ccbogel/QualCoder
https://qualcoder.wordpress.com/
'''

from copy import deepcopy
import datetime
import logging
import os
import platform
from random import randint
import sys
import traceback

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush

from add_item_name import DialogAddItemName
from color_selector import DialogColorSelect
from color_selector import colors
from confirm_delete import DialogConfirmDelete
from GUI.ui_dialog_code_av import Ui_Dialog_code_av
from GUI.ui_dialog_view_av import Ui_Dialog_view_av
from memo import DialogMemo
from select_file import DialogSelectFile
import vlc

path = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger(__name__)


def exception_handler(exception_type, value, tb_obj):
    """ Global exception handler useful in GUIs.
    tb_obj: exception.__traceback__ """
    tb = '\n'.join(traceback.format_tb(tb_obj))
    text = 'Traceback (most recent call last):\n' + tb + '\n' + exception_type.__name__ + ': ' + str(value)
    print(text)
    logger.error("Uncaught exception:\n" + text)
    QtWidgets.QMessageBox.critical(None, 'Uncaught Exception ', text)


class DialogCodeAV(QtWidgets.QDialog):
    """ View and code audio and video segments.
    Create codes and categories.  """

    settings = None
    filename = None
    files = []
    file_ = None
    codes = []
    categories = []
    segments = []
    ddialog = None
    media_data = None
    instance = None
    media_player = None
    media = None
    segment = {}

    def __init__(self, settings):
        """ Show list of audio and video files.
        Can create a transcribe file from the audio / video.
        """

        #TODO maybe show other coders ?
        #TODO add a graphical view of coded segments

        sys.excepthook = exception_handler
        self.settings = settings
        self.codes = []
        self.categories = []
        self.segments = []
        self.media_data = None
        self.segment['start'] = None
        self.segment['end'] = None
        self.get_codes_categories()
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_code_av()
        self.ui.setupUi(self)
        self.ui.splitter.setSizes([100, 200])
        # until any media is selected disable some widgets
        self.ui.pushButton_play.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(False)
        self.ui.pushButton_coding.setEnabled(False)
        self.ui.horizontalSlider.setEnabled(False)
        self.ui.pushButton_memo.setEnabled(False)
        self.ui.textEdit.setReadOnly(True)
        newfont = QtGui.QFont(settings['font'], settings['fontsize'], QtGui.QFont.Normal)
        self.setFont(newfont)
        treefont = QtGui.QFont(settings['font'], settings['treefontsize'], QtGui.QFont.Normal)
        self.ui.treeWidget.setFont(treefont)
        self.ui.label_coder.setText("Coder: " + settings['codername'])
        self.setWindowTitle("Media coding")
        self.ui.pushButton_select.pressed.connect(self.select_media)
        self.ui.pushButton_memo.pressed.connect(self.segment_memo)
        #TODO show other coders, maybe?
        #self.ui.checkBox_show_coders.stateChanged.connect(self.show_or_hide_coders)
        self.ui.treeWidget.setDragEnabled(True)
        self.ui.treeWidget.setAcceptDrops(True)
        self.ui.treeWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.ui.treeWidget.viewport().installEventFilter(self)
        self.ui.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeWidget.customContextMenuRequested.connect(self.tree_menu)
        self.fill_tree()

        # My solution to getting gui mouse events by putting vlc video in another dialog
        # Otherwise, the vlc player hogs all the mouse events
        self.ddialog = QtWidgets.QDialog()
        self.ddialog.resize(640, 480)
        self.ddialog.gridLayout = QtWidgets.QGridLayout(self.ddialog)
        self.ddialog.dframe = QtWidgets.QFrame(self.ddialog)
        self.ddialog.dframe.setObjectName("frame")
        if platform.system() == "Darwin":  # for MacOS
            self.ddialog.dframe = QtWidgets.QMacCocoaViewContainer(0)
        self.palette = self.ddialog.dframe.palette()
        self.palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
        self.ddialog.dframe.setPalette(self.palette)
        self.ddialog.dframe.setAutoFillBackground(True)
        self.ddialog.gridLayout.addWidget(self.ddialog.dframe, 0, 0, 0, 0)
        self.ddialog.move(self.mapToGlobal(QtCore.QPoint(50, -200)))
        self.ddialog.show()

        # Create a vlc instance with an empty vlc media player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        self.mediaplayer.video_set_mouse_input(False)
        self.mediaplayer.video_set_key_input(False)

        self.ui.horizontalSlider.sliderMoved.connect(self.set_position)
        #self.ui.horizontalSlider.sliderPressed.connect(self.set_position)
        self.ui.pushButton_play.clicked.connect(self.play_pause)
        self.ui.pushButton_stop.clicked.connect(self.stop)
        self.ui.horizontalSlider_vol.valueChanged.connect(self.set_volume)
        self.ui.pushButton_coding.pressed.connect(self.create_or_clear_segment)

        # set the scene for coding stripes
        self.scene = GraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)

        msg = "Currently, deleting segments can only be achieved through the sql dialog."
        QtWidgets.QMessageBox.warning(None, 'UNDER DEVELOPMENT', msg)

    def get_codes_categories(self):
        """ Called from init, delete category/code. """

        self.categories = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, catid, owner, date, memo, supercatid from code_cat")
        result = cur.fetchall()
        for row in result:
            self.categories.append({'name': row[0], 'catid': row[1], 'owner': row[2],
            'date': row[3], 'memo': row[4], 'supercatid': row[5]})
        self.codes = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, memo, owner, date, cid, catid, color from code_name")
        result = cur.fetchall()
        for row in result:
            self.codes.append({'name': row[0], 'memo': row[1], 'owner': row[2], 'date': row[3],
            'cid': row[4], 'catid': row[5], 'color': row[6]})

    def fill_tree(self):
        """ Fill tree widget, tope level items are main categories and unlinked codes. """

        cats = deepcopy(self.categories)
        codes = deepcopy(self.codes)
        self.ui.treeWidget.clear()
        self.ui.treeWidget.setColumnCount(3)
        self.ui.treeWidget.setHeaderLabels(["Name", "Id", "Memo"])
        self.ui.treeWidget.setColumnHidden(1, True)
        self.ui.treeWidget.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.treeWidget.header().setStretchLastSection(False)
        # add top level categories
        remove_list = []
        for c in cats:
            if c['supercatid'] is None:
                memo = ""
                if c['memo'] != "":
                    memo = "Memo"
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']), memo])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                top_item.setToolTip(0, c['owner'] + "\n" + c['date'])
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_list.append(c)
        for item in remove_list:
            #try:
            cats.remove(item)
            #except Exception as e:
            #    print(e, item)

        ''' Add child categories. Look at each unmatched category, iterate through tree
        to add as child, then remove matched categories from the list. '''
        count = 0
        while len(cats) > 0 or count < 10000:
            remove_list = []
            #logger.debug("cats:" + str(cats))
            for c in cats:
                it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
                item = it.value()
                while item:  # while there is an item in the list
                    if item.text(1) == 'catid:' + str(c['supercatid']):
                        memo = ""
                        if c['memo'] != "":
                            memo = "Memo"
                        child = QtWidgets.QTreeWidgetItem([c['name'], 'catid:' + str(c['catid']), memo])
                        child.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
                        child.setToolTip(0, c['owner'] + "\n" + c['date'])
                        item.addChild(child)
                        remove_list.append(c)
                    it += 1
                    item = it.value()
            for item in remove_list:
                cats.remove(item)
            count += 1

        # add unlinked codes as top level items
        remove_items = []
        for c in codes:
            if c['catid'] is None:
                memo = ""
                if c['memo'] != "":
                    memo = "Memo"
                top_item = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']), memo])
                top_item.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                top_item.setToolTip(0, c['owner'] + "\n" + c['date'])
                top_item.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                top_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
                self.ui.treeWidget.addTopLevelItem(top_item)
                remove_items.append(c)
        for item in remove_items:
            codes.remove(item)

        # add codes as children
        for c in codes:
            it = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
            item = it.value()
            while item:
                if item.text(1) == 'catid:' + str(c['catid']):
                    memo = ""
                    if c['memo'] != "":
                        memo = "Memo"
                    child = QtWidgets.QTreeWidgetItem([c['name'], 'cid:' + str(c['cid']), memo])
                    child.setBackground(0, QBrush(QtGui.QColor(c['color']), Qt.SolidPattern))
                    child.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
                    child.setToolTip(0, c['owner'] + "\n" + c['date'])
                    child.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
                    item.addChild(child)
                    c['catid'] = -1  # make unmatchable
                it += 1
                item = it.value()
        self.ui.treeWidget.expandAll()

    def select_media(self):
        """ Get all the media files. A dialog of filenames is presented to the user.
        The selected media file is then displayed for coding. """

        media_files = []
        cur = self.settings['conn'].cursor()
        cur.execute("select name, id, memo, owner, date, mediapath from source where \
            substr(mediapath,1,6) in ('/audio','/video') order by name")
        result = cur.fetchall()
        for row in result:
            media_files.append({'name': row[0], 'id': row[1], 'memo': row[2],
                'owner': row[3], 'date': row[4], 'mediapath': row[5]})

        ui = DialogSelectFile(media_files, "Select file to view", "single")
        ok = ui.exec_()
        if not ok:
            return
        self.media_data = ui.get_selected()
        self.ui.pushButton_play.setEnabled(True)
        self.ui.pushButton_stop.setEnabled(True)
        self.ui.horizontalSlider.setEnabled(True)
        self.ui.pushButton_coding.setEnabled(True)
        self.load_media()
        self.load_segments()

    def load_segments(self):
        """ Get coded segments for this file, for this coder, or all coders.
        Currently only for this coder. Called from select_media. """

        self.segments = []
        sql = "select avid, id, pos0, pos1, code_av.cid, code_av.memo, code_av.date, "
        sql += " code_av.owner, code_name.name, code_name.color from code_av"
        sql += " join code_name on code_name.cid=code_av.cid"
        sql += " where id=? "
        #if not self.ui.checkBox_show_coders.isChecked():
        sql += " and code_av.owner=? "
        values = [self.media_data['id']]
        values.append(self.settings['codername'])
        cur = self.settings['conn'].cursor()
        cur.execute(sql, values)
        code_results = cur.fetchall()
        for row in code_results:
            self.segments.append({'avid': row[0], 'id': row[1], 'pos0': row[2],
            'pos1': row[3], 'cid':row[4], 'memo': row[5], 'date': row[6],
            'owner': row[7], 'codename': row[8], 'color': row[9]})

        for s in self.segments:
            print(s)
        #TODO draw coded segments in scene
        scaler = 990 / self.media.get_duration()
        self.scene.clear()
        for s in self.segments:
            self.scene.addItem(SegmentGraphicsItem(s, scaler))

    def load_media(self):
        """ Add media to media dialog. """

        self.ddialog.setWindowTitle(self.media_data['mediapath'])
        self.setWindowTitle(self.media_data['mediapath'])
        try:
            self.media = self.instance.media_new(self.settings['path'] + self.media_data['mediapath'])
        except Exception as e:
            QtWidgets.QMessageBox.warning(None, "Media not found",
                str(e) +"\n" + self.settings['path'] + self.media_data['mediapath'])
            self.closeEvent()
            return

        # Put the media in the media player
        self.mediaplayer.set_media(self.media)
        # Parse the metadata of the file
        self.media.parse()
        self.mediaplayer.video_set_mouse_input(False)
        self.mediaplayer.video_set_key_input(False)
        # The media player has to be connected to the QFrame (otherwise the
        # video would be displayed in it's own window). This is platform
        # specific, so we must give the ID of the QFrame (or similar object) to
        # vlc. Different platforms have different functions for this
        if platform.system() == "Linux": # for Linux using the X Server
            #self.mediaplayer.set_xwindow(int(self.ui.frame.winId()))
            self.mediaplayer.set_xwindow(int(self.ddialog.dframe.winId()))
        elif platform.system() == "Windows": # for Windows
            self.mediaplayer.set_hwnd(int(self.ui.frame.winId()))
        elif platform.system() == "Darwin": # for MacOS
            self.mediaplayer.set_nsobject(int(self.ui.frame.winId()))
        msecs = self.media.get_duration()
        secs = int(msecs / 1000)
        mins = int(secs / 60)
        remainder_secs = secs - mins * 60
        self.media_duration_text = "Duration: " + str(mins) + "." + str(remainder_secs)
        self.ui.label_time_2.setText(self.media_duration_text)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        # Get the transcribe text and fill textedit
        cur = self.settings['conn'].cursor()
        cur.execute("select id, fulltext from source where name = ?", [self.media_data['name'] + ".transcribed"])
        self.transcription = cur.fetchone()
        if self.transcription is not None:
            self.ui.textEdit.setText(self.transcription[1])
        #self.play_pause()

    def set_position(self):
        """ Set the movie position according to the position slider.
        The vlc MediaPlayer needs a float value between 0 and 1, Qt uses
        integer variables, so you need a factor; the higher the factor, the
        more precise are the results (1000 should suffice).
        """

        # Set the media position to where the slider was dragged
        self.timer.stop()
        pos = self.ui.horizontalSlider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()

    def play_pause(self):
        """ Toggle play or pause status. """

        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.ui.pushButton_play.setText("Play")
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            self.ui.pushButton_play.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """ Stop vlc player. """

        self.mediaplayer.stop()
        self.ui.pushButton_play.setText("Play")

    def set_volume(self, volume):
        """ Set the volume. """

        self.mediaplayer.audio_set_volume(volume)

    def update_ui(self):
        """ Updates the user interface. """

        # Set the slider's position to its corresponding media position
        # Note that the setValue function only takes values of type int,
        # so we must first convert the corresponding media position.
        media_pos = int(self.mediaplayer.get_position() * 1000)
        self.ui.horizontalSlider.setValue(media_pos)

        # update label_time
        msecs = self.mediaplayer.get_time()
        secs = int(msecs / 1000)
        mins = int(secs / 60)
        remainder_secs = str(secs - mins * 60)
        if len(remainder_secs) == 1:
            remainder_secs = "0" + remainder_secs
        self.ui.label_time.setText("Time: " + str(mins) + "." + remainder_secs)

        # No need to call this function if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.stop()
            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused:
                self.stop()

    def closeEvent(self, event):
        """ Stop the vlc player on close. """

        self.ddialog.close()
        self.stop()

    def segment_memo(self):
        """ Create a memo for the segment.
        Opened via pushButton. PushButton only avaialable when a segment start and end
        positions are defined.  """

        ui = DialogMemo(self.settings, "Memo for segment", "")
        ui.exec_()
        self.segment['memo'] = ui.memo

    def create_or_clear_segment(self):
        """ Make the start end end points of the segment of time.
        Use minutes and seconds, and milliseconds formats for the time.
        Can also clear the segment by pressing the button when it says Clear segement.
        clear segment text is changed to Start segment once a segment is assigned to a code.
        """

        if self.ui.pushButton_coding.text() == "Clear segment":
            self.segment['start'] = None
            self.segment['end'] = None
            self.segment['start_msecs'] = None
            self.segment['end_msecs'] = None
            self.segment['memo'] = ""
            self.ui.pushButton_coding.setText("Start segment")
            self.ui.label_segment.setText("Segment:")
            return
        time = self.ui.label_time.text()
        time = time[6:]
        time_msecs = self.mediaplayer.get_time()
        if self.segment['start'] is None:
            self.segment['start'] = time
            self.segment['start_msecs'] = time_msecs
            self.segment['memo'] = ""
            self.ui.pushButton_coding.setText("End segment")
            self.ui.label_segment.setText("Segment: " + str(self.segment['start']) + " - ")
            return
        if self.segment['start'] is not None and self.segment['end'] is None:
            self.segment['end'] = time
            self.segment['end_msecs'] = time_msecs
            self.ui.pushButton_coding.setText("Clear segment")
            self.ui.pushButton_memo.setEnabled(True)

            # check and reverse start and end times if start is greater than the end
            if float(self.segment['start']) > float(self.segment['end']):
                tmp = self.segment['start']
                tmp_msecs = self.segment['start_msecs']
                self.segment['start'] = self.segment['end']
                self.segment['start_msecs'] = self.segment['end_msecs']
                self.segment['end'] = tmp
                self.segment['end_msecs'] = tmp_msecs
                self.ui.pushButton_memo.setEnabled(True)
            text = "Segment: " + str(self.segment['start']) + " - " + self.segment['end']
            self.ui.label_segment.setText(text)

    def tree_menu(self, position):
        """ Context menu for treewidget items.
        Add, rename, memo, move or delete code or category. Change code color. """

        menu = QtWidgets.QMenu()
        selected = self.ui.treeWidget.currentItem()
        #print(selected.parent())
        #index = self.ui.treeWidget.currentIndex()
        ActionItemAssignSegment = None
        if self.segment['end'] is not None:
            ActionItemAssignSegment = menu.addAction("Assign segment to code")
        ActionItemAddCode = menu.addAction("Add a new code")
        ActionItemAddCategory = menu.addAction("Add a new category")
        ActionItemRename = menu.addAction("Rename")
        ActionItemEditMemo = menu.addAction("View or edit memo")
        ActionItemDelete = menu.addAction("Delete")
        if selected is not None and selected.text(1)[0:3] == 'cid':
            ActionItemChangeColor = menu.addAction("Change code color")

        action = menu.exec_(self.ui.treeWidget.mapToGlobal(position))
        if selected is not None and selected.text(1)[0:3] == 'cid' and action == ActionItemChangeColor:
            self.change_code_color(selected)
        if action == ActionItemAddCategory:
            self.add_category()
        if action == ActionItemAddCode:
            self.add_code()
        if selected is not None and action == ActionItemRename:
            self.rename_category_or_code(selected)
        if selected is not None and action == ActionItemEditMemo:
            self.add_edit_code_memo(selected)
        if selected is not None and action == ActionItemDelete:
            self.delete_category_or_code(selected)
        # UnboundLocalError
        if action == ActionItemAssignSegment:
            self.assign_segment_to_code(selected)

    def eventFilter(self, object, event):
        """ Using this event filter to identify treeWidgetItem drop events.
        http://doc.qt.io/qt-5/qevent.html#Type-enum
        QEvent::Drop	63	A drag and drop operation is completed (QDropEvent).
        https://stackoverflow.com/questions/28994494/why-does-qtreeview-not-fire-a-drop-or-move-event-during-drag-and-drop
        Also use eventFilter for QGraphicsView.
        """

        if object is self.ui.treeWidget.viewport():
            if event.type() == QtCore.QEvent.Drop:
                item = self.ui.treeWidget.currentItem()
                parent = self.ui.treeWidget.itemAt(event.pos())
                self.item_moved_update_data(item, parent)
                self.get_codes_categories()
                self.fill_tree()
        return False

    def assign_segment_to_code(self, selected):
        """ Assign time segment to selected code. Insert an entry into the database.
        Then clear the segment for re-use."""

        sql = "insert into code_av (id, pos0, pos1, cid, memo, date, owner) values(?,?,?,?,?,?,?)"
        cid = int(selected.text(1).split(':')[1])
        values = [self.media_data['id'], self.segment['start_msecs'],
            self.segment['end_msecs'], cid, self.segment['memo'],
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.settings['codername']]
        cur = self.settings['conn'].cursor()
        cur.execute(sql, values)
        self.settings['conn'].commit()
        self.load_segments()

        self.segment['start'] = None
        self.segment['start_msecs'] = None
        self.segment['end'] = None
        self.segment['end_msecs'] = None
        self.segment['memo'] = ""
        self.ui.label_segment.setText("Segment:")
        self.ui.pushButton_coding.setText("Start segment")
        self.ui.pushButton_memo.setEnabled(False)

    def item_moved_update_data(self, item, parent):
        """ Called from drop event in treeWidget view port.
        identify code or category to move.
        Also merge codes if one code is dropped on another code. """

        # find the category in the list
        if item.text(1)[0:3] == 'cat':
            found = -1
            for i in range(0, len(self.categories)):
                if self.categories[i]['catid'] == int(item.text(1)[6:]):
                    found = i
            if found == -1:
                return
            if parent is None:
                self.categories[found]['supercatid'] = None
            else:
                if parent.text(1).split(':')[0] == 'cid':
                    # parent is code (leaf) cannot add child
                    return
                supercatid = int(parent.text(1).split(':')[1])
                if supercatid == self.categories[found]['catid']:
                    # something went wrong
                    logger.debug("supercatid== self.categories[found][catid]")
                    return
                self.categories[found]['supercatid'] = supercatid
            cur = self.settings['conn'].cursor()
            cur.execute("update code_cat set supercatid=? where catid=?",
            [self.categories[found]['supercatid'], self.categories[found]['catid']])
            self.settings['conn'].commit()

        # find the code in the list
        if item.text(1)[0:3] == 'cid':
            found = -1
            for i in range(0, len(self.codes)):
                if self.codes[i]['cid'] == int(item.text(1)[4:]):
                    found = i
            if found == -1:
                return
            if parent is None:
                self.codes[found]['catid'] = None
            else:
                if parent.text(1).split(':')[0] == 'cid':
                    # parent is code (leaf) cannot add child, but can merge
                    self.merge_codes(self.codes[found], parent)
                    return
                catid = int(parent.text(1).split(':')[1])
                self.codes[found]['catid'] = catid

            cur = self.settings['conn'].cursor()
            cur.execute("update code_name set catid=? where cid=?",
            [self.codes[found]['catid'], self.codes[found]['cid']])
            self.settings['conn'].commit()

    def merge_codes(self, item, parent):
        """ Merge code or category with another code or category.
        Called by item_moved_update_data when a code is moved onto another code. """

        msg = "Merge code: " + item['name'] + "\ninto code: " + parent.text(0)
        reply = QtWidgets.QMessageBox.question(None, 'Merge codes',
        msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No:
            return
        cur = self.settings['conn'].cursor()
        old_cid = item['cid']
        new_cid = int(parent.text(1).split(':')[1])
        try:
            cur.execute("update code_text set cid=? where cid=?", [new_cid, old_cid])
            self.settings['conn'].commit()
        except Exception as e:
            e = str(e)
            msg = "cannot merge codes, unmark overlapping text first.\n" + e
            QtWidgets.QInformationDialog(None, "Cannot merge", msg)
            return
        cur.execute("delete from code_name where cid=?", [old_cid, ])
        self.settings['conn'].commit()

    def add_code(self):
        """ Use add_item dialog to get new code text.
        Add_code_name dialog checks for duplicate code name.
        New code is added to data and database. """

        ui = DialogAddItemName(self.codes, "Add new code")
        ui.exec_()
        newCodeText = ui.get_new_name()
        if newCodeText is None:
            return
        code_color = colors[randint(0, len(colors) - 1)]
        item = {'name': newCodeText, 'memo': "", 'owner': self.settings['codername'],
        'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),'catid': None, 'color': code_color}
        cur = self.settings['conn'].cursor()
        cur.execute("insert into code_name (name,memo,owner,date,catid,color) values(?,?,?,?,?,?)"
            , (item['name'], item['memo'], item['owner'], item['date'], item['catid'], item['color']))
        self.settings['conn'].commit()
        cur.execute("select last_insert_rowid()")
        cid = cur.fetchone()[0]
        item['cid'] = cid
        self.codes.append(item)
        top_item = QtWidgets.QTreeWidgetItem([item['name'], 'cid:' + str(item['cid']), ""])
        top_item.setIcon(0, QtGui.QIcon("GUI/icon_code.png"))
        color = item['color']
        top_item.setBackground(0, QBrush(QtGui.QColor(color), Qt.SolidPattern))
        self.ui.treeWidget.addTopLevelItem(top_item)
        self.ui.treeWidget.setCurrentItem(top_item)

    def add_category(self):
        """ Add a new category.
        Note: the addItem dialog does the checking for duplicate category names
        Add the new category as a top level item. """

        ui = DialogAddItemName(self.categories, "Category")
        ui.exec_()
        newCatText = ui.get_new_name()
        if newCatText is None:
            return
        # add to database
        item = {'name': newCatText, 'cid': None, 'memo': "",
        'owner': self.settings['codername'],
        'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        cur = self.settings['conn'].cursor()
        cur.execute("insert into code_cat (name, memo, owner, date, supercatid) values(?,?,?,?,?)"
            , (item['name'], item['memo'], item['owner'], item['date'], None))
        self.settings['conn'].commit()
        cur.execute("select last_insert_rowid()")
        catid = cur.fetchone()[0]
        item['catid'] = catid
        self.categories.append(item)
        # update widget
        top_item = QtWidgets.QTreeWidgetItem([item['name'], 'catid:' + str(item['catid']), ""])
        top_item.setIcon(0, QtGui.QIcon("GUI/icon_cat.png"))
        self.ui.treeWidget.addTopLevelItem(top_item)

    def delete_category_or_code(self, selected):
        """ Determine if category or code is to be deleted. """

        if selected.text(1)[0:3] == 'cat':
            self.delete_category(selected)
            return  # avoid error as selected is now None
        if selected.text(1)[0:3] == 'cid':
            self.delete_code(selected)

    def delete_code(self, selected):
        """ Find code, remove from database, refresh and code_name data and fill
        treeWidget. """

        # find the code_in the list, check to delete
        found = -1
        for i in range(0, len(self.codes)):
            if self.codes[i]['cid'] == int(selected.text(1)[4:]):
                found = i
        if found == -1:
            return
        code_ = self.codes[found]
        ui = DialogConfirmDelete("Code: " + selected.text(0))
        ok = ui.exec_()
        if not ok:
            return
        cur = self.settings['conn'].cursor()
        cur.execute("delete from code_name where cid=?", [code_['cid'], ])
        cur.execute("delete from code_text where cid=?", [code_['cid'], ])
        self.settings['conn'].commit()
        selected = None
        self.get_codes_categories()
        self.fill_tree()

    def delete_category(self, selected):
        """ Find category, remove from database, refresh categories and code data
        and fill treeWidget. """

        found = -1
        for i in range(0, len(self.categories)):
            if self.categories[i]['catid'] == int(selected.text(1)[6:]):
                found = i
        if found == -1:
            return
        category = self.categories[found]
        ui = DialogConfirmDelete("Category: " + selected.text(0))
        ok = ui.exec_()
        if not ok:
            return
        cur = self.settings['conn'].cursor()
        cur.execute("update code_name set catid=null where catid=?", [category['catid'], ])
        cur.execute("update code_cat set supercatid=null where catid = ?", [category['catid'], ])
        cur.execute("delete from code_cat where catid = ?", [category['catid'], ])
        self.settings['conn'].commit()
        selected = None
        self.get_codes_categories()
        self.fill_tree()

    def add_edit_code_memo(self, selected):
        """ View and edit a memo. """

        if selected.text(1)[0:3] == 'cid':
            # find the code in the list
            found = -1
            for i in range(0, len(self.codes)):
                if self.codes[i]['cid'] == int(selected.text(1)[4:]):
                    found = i
            if found == -1:
                return
            ui = DialogMemo(self.settings, "Memo for Code " + self.codes[found]['name'],
            self.codes[found]['memo'])
            ui.exec_()
            memo = ui.memo
            if memo == "":
                selected.setData(2, QtCore.Qt.DisplayRole, "")
            else:
                selected.setData(2, QtCore.Qt.DisplayRole, "Memo")
            # update codes list and database
            if memo != self.codes[found]['memo']:
                self.codes[found]['memo'] = memo
                cur = self.settings['conn'].cursor()
                cur.execute("update code_name set memo=? where cid=?", (memo, self.codes[found]['cid']))
                self.settings['conn'].commit()

        if selected.text(1)[0:3] == 'cat':
            # find the category in the list
            found = -1
            for i in range(0, len(self.categories)):
                if self.categories[i]['catid'] == int(selected.text(1)[6:]):
                    found = i
            if found == -1:
                return
            ui = DialogMemo(self.settings, "Memo for Category " + self.categories[found]['name'],
            self.categories[found]['memo'])
            ui.exec_()
            memo = ui.memo
            if memo == "":
                selected.setData(2, QtCore.Qt.DisplayRole, "")
            else:
                selected.setData(2, QtCore.Qt.DisplayRole, "Memo")
            # update codes list and database
            if memo != self.categories[found]['memo']:
                self.categories[found]['memo'] = memo
                cur = self.settings['conn'].cursor()
                cur.execute("update code_cat set memo=? where catid=?", (memo, self.categories[found]['catid']))
                self.settings['conn'].commit()

    def rename_category_or_code(self, selected):
        """ Rename a code or category. Checks that the proposed code or category name is
        not currently in use. """

        if selected.text(1)[0:3] == 'cid':
            new_text, ok = QtWidgets.QInputDialog.getText(self, "Rename code", "New code name:",
            QtWidgets.QLineEdit.Normal, selected.text(0))
            if not ok or new_text == '':
                return
            # check that no other code has this text
            for c in self.codes:
                if c['name'] == new_text:
                    QtWidgets.QMessageBox.warning(None, "Name in use",
                    new_text + " is already in use, choose another name ", QtWidgets.QMessageBox.Ok)
                    return
            # find the code in the list
            found = -1
            for i in range(0, len(self.codes)):
                if self.codes[i]['cid'] == int(selected.text(1)[4:]):
                    found = i
            if found == -1:
                return
            # update codes list and database
            cur = self.settings['conn'].cursor()
            cur.execute("update code_name set name=? where cid=?", (new_text, self.codes[found]['cid']))
            self.settings['conn'].commit()
            self.codes[found]['name'] = new_text
            selected.setData(0, QtCore.Qt.DisplayRole, new_text)
            return

        if selected.text(1)[0:3] == 'cat':
            new_text, ok = QtWidgets.QInputDialog.getText(self, "Rename category", "New category name:",
            QtWidgets.QLineEdit.Normal, selected.text(0))
            if not ok or new_text == '':
                return
            # check that no other category has this text
            for c in self.categories:
                if c['name'] == new_text:
                    msg = "This code name is already in use"
                    QtWidgets.QMessageBox.warning(None, "Duplicate code name", msg, QtWidgets.QMessageBox.Ok)
                    return
            # find the category in the list
            found = -1
            for i in range(0, len(self.categories)):
                if self.categories[i]['catid'] == int(selected.text(1)[6:]):
                    found = i
            if found == -1:
                return
            # update category list and database
            cur = self.settings['conn'].cursor()
            cur.execute("update code_cat set name=? where catid=?",
            (new_text, self.categories[found]['catid']))
            self.settings['conn'].commit()
            self.categories[found]['name'] = new_text
            selected.setData(0, QtCore.Qt.DisplayRole, new_text)

    def change_code_color(self, selected):
        """ Change the color of the currently selected code. """

        cid = int(selected.text(1)[4:])
        found = -1
        for i in range(0, len(self.codes)):
            if self.codes[i]['cid'] == cid:
                found = i
        if found == -1:
            return
        ui = DialogColorSelect(self.codes[found]['color'])
        ok = ui.exec_()
        if not ok:
            return
        new_color = ui.get_color()
        if new_color is None:
            return
        #print(new_color)
        selected.setBackground(0, QBrush(QtGui.QColor(new_color), Qt.SolidPattern))
        #update codes list and database
        self.codes[found]['color'] = new_color
        cur = self.settings['conn'].cursor()
        cur.execute("update code_name set color=? where cid=?",
        (self.codes[found]['color'], self.codes[found]['cid']))
        self.settings['conn'].commit()


class GraphicsScene(QtWidgets.QGraphicsScene):
    """ set the scene for the graphics objects and re-draw events. """

    # matches the designer file graphics view
    sceneWidth = 990
    sceneHeight = 110

    def __init__ (self, parent=None):
        super(GraphicsScene, self).__init__ (parent)
        self.setSceneRect(QtCore.QRectF(0, 0, self.sceneWidth, self.sceneHeight))

    def setWidth(self, width):
        """ Resize scene width. """

        self.sceneWidth = width
        self.setSceneRect(QtCore.QRectF(0, 0, self.sceneWidth, self.sceneHeight))

    def setHeight(self, height):
        """ Resize scene height. """

        self.sceneHeight = height
        self.setSceneRect(QtCore.QRectF(0, 0, self.sceneWidth, self.sceneHeight))

    def getWidth(self):
        """ Return scene width. """

        return self.sceneWidth

    def getHeight(self):
        """ Return scene height. """

        return self.sceneHeight

    """def mouseMoveEvent(self, mouseEvent):
        super(GraphicsScene, self).mousePressEvent(mouseEvent)

        for item in self.items():
            if isinstance(item, TextGraphicsItem):
                item.data['x'] = item.pos().x()
                item.data['y'] = item.pos().y()
                #logger.debug("item pos:" + str(item.pos()))
        for item in self.items():
            if isinstance(item, LinkGraphicsItem):
                item.redraw()
        self.update()"""

    """def mousePressEvent(self, mouseEvent):
        super(GraphicsScene, self).mousePressEvent(mouseEvent)
        #position = QtCore.QPointF(event.scenePos())
        #logger.debug("pressed here: " + str(position.x()) + ", " + str(position.y()))
        for item in self.items(): # item is QGraphicsProxyWidget
            if isinstance(item, LinkItem):
                item.redraw()
        self.update(self.sceneRect())"""

    """def mouseReleaseEvent(self, mouseEvent):
        ''' On mouse release, an item might be repositioned so need to redraw all the
        link_items '''

        super(GraphicsScene, self).mouseReleaseEvent(mouseEvent)
        for item in self.items():
            if isinstance(item, LinkGraphicsItem):
                item.redraw()
        self.update(self.sceneRect())"""


class SegmentGraphicsItem(QtWidgets.QGraphicsLineItem):
    """ Draws coded segment line. Uses the media duration to scale the line length.
    y values will change depending on how many different codes are shown.
    TODO y values will need to be supplied. """

    segment = None
    scaler = None

    def __init__(self, segment, scaler):
        super(SegmentGraphicsItem, self).__init__(None)

        self.segment = segment
        self.scaler = scaler
        self.setFlag(self.ItemIsSelectable, True)
        tooltip = self.segment['codename']
        #TODO add start and end times
        if self.segment['memo'] != "":
            tooltip += "\nMemo: " + self.segment['memo']
        self.setToolTip(tooltip)
        self.calculatePointsAndDraw()

    def redraw(self):
        """ Called from mouse move and release events. """

        self.calculatePointsAndDraw()

    def calculatePointsAndDraw(self):
        """ Calculate the x values for the line. """

        from_x = self.segment['pos0'] * self.scaler
        to_x = self.segment['pos1'] * self.scaler
        print("from_x", from_x, self.segment['pos0'], self.scaler)
        #TODO y values
        y = 10
        line_width = 8
        color = QtGui.QColor(self.segment['color'])
        self.setPen(QtGui.QPen(color, line_width, QtCore.Qt.SolidLine))
        self.setLine(from_x, y, to_x, y)


class DialogViewAV(QtWidgets.QDialog):
    """ View Audio and Video using VLC. View and edit displayed memo.
    Mouse events did not work when the vlc play is in this dialog.
    Mouse events do work with the vlc player in a separate modal dialog.
    """

    settings = None
    label = None
    media_data = None
    is_paused = False
    media_duration_text = ""
    displayframe = None
    ddialog = None
    instance = None
    mediaplayer = None
    media = None
    transcription = None

    def __init__(self, settings, media_data, parent=None):

        """ Media_data contains: {name, mediapath, owner, id, date, memo, fulltext}
        A separate modal dialog is created to display the video.
        """

        sys.excepthook = exception_handler
        self.settings = settings
        self.media_data = media_data
        self.is_paused = True

        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_view_av()
        self.ui.setupUi(self)
        newfont = QtGui.QFont(settings['font'], settings['fontsize'], QtGui.QFont.Normal)
        self.setFont(newfont)
        self.setWindowTitle(self.media_data['mediapath'])

        # Get the transcribe text and fill textedit
        cur = self.settings['conn'].cursor()
        cur.execute("select id, fulltext from source where name = ?", [media_data['name'] + ".transcribed"])
        self.transcription = cur.fetchone()
        if self.transcription is not None:
            self.ui.textEdit_transcription.setText(self.transcription[1])

        # My solution to getting gui mouse events by putting vlc video in another dialog
        self.ddialog = QtWidgets.QDialog()
        self.ddialog.setWindowTitle(self.media_data['mediapath'])
        self.ddialog.resize(640, 480)
        self.ddialog.gridLayout = QtWidgets.QGridLayout(self.ddialog)
        self.ddialog.dframe = QtWidgets.QFrame(self.ddialog)
        self.ddialog.dframe.setObjectName("frame")
        if platform.system() == "Darwin": # for MacOS
            self.ddialog.dframe = QtWidgets.QMacCocoaViewContainer(0)
        self.palette = self.ddialog.dframe.palette()
        self.palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
        self.ddialog.dframe.setPalette(self.palette)
        self.ddialog.dframe.setAutoFillBackground(True)
        self.ddialog.gridLayout.addWidget(self.ddialog.dframe, 0, 0, 0, 0)
        self.ddialog.move(self.mapToGlobal(QtCore.QPoint(50, -200)))
        self.ddialog.show()

        # Create a basic vlc instance
        self.instance = vlc.Instance()
        # Create an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()
        self.mediaplayer.video_set_mouse_input(False)
        self.mediaplayer.video_set_key_input(False)

        self.ui.horizontalSlider.sliderMoved.connect(self.set_position)
        self.ui.horizontalSlider.sliderPressed.connect(self.set_position)
        self.ui.pushButton_play.clicked.connect(self.play_pause)
        self.ui.pushButton_stop.clicked.connect(self.stop)
        self.ui.horizontalSlider_vol.valueChanged.connect(self.set_volume)

        try:
            self.media = self.instance.media_new(self.settings['path'] + self.media_data['mediapath'])
        except Exception as e:
            QtWidgets.QMessageBox.warning(None, "Media not found",
                str(e) +"\n" + self.settings['path'] + self.media_data['mediapath'])
            self.closeEvent()
            return

        # Put the media in the media player
        self.mediaplayer.set_media(self.media)
        # Parse the metadata of the file
        self.media.parse()
        self.mediaplayer.video_set_mouse_input(False)
        self.mediaplayer.video_set_key_input(False)
        # The media player has to be connected to the QFrame (otherwise the
        # video would be displayed in it's own window). This is platform
        # specific, so we must give the ID of the QFrame (or similar object) to
        # vlc. Different platforms have different functions for this
        if platform.system() == "Linux": # for Linux using the X Server
            #self.mediaplayer.set_xwindow(int(self.ui.frame.winId()))
            self.mediaplayer.set_xwindow(int(self.ddialog.dframe.winId()))
        elif platform.system() == "Windows": # for Windows
            self.mediaplayer.set_hwnd(int(self.ui.frame.winId()))
        elif platform.system() == "Darwin": # for MacOS
            self.mediaplayer.set_nsobject(int(self.ui.frame.winId()))

        msecs = self.media.get_duration()
        secs = int(msecs / 1000)
        mins = int(secs / 60)
        remainder_secs = secs - mins * 60
        self.media_duration_text = "Duration: " + str(mins) + "." + str(remainder_secs)
        self.ui.label_time_2.setText(self.media_duration_text)
        self.ui.textEdit.setText(self.media_data['memo'])
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        #self.play_pause()

    def set_position(self):
        """ Set the movie position according to the position slider.
        The vlc MediaPlayer needs a float value between 0 and 1, Qt uses
        integer variables, so you need a factor; the higher the factor, the
        more precise are the results (1000 should suffice).
        """

        # Set the media position to where the slider was dragged
        self.timer.stop()
        pos = self.ui.horizontalSlider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()

    def play_pause(self):
        """ Toggle play or pause status. """

        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.ui.pushButton_play.setText("Play")
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            self.ui.pushButton_play.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """ Stop player. """

        self.mediaplayer.stop()
        self.ui.pushButton_play.setText("Play")

    def set_volume(self, volume):
        """ Set the volume. """

        self.mediaplayer.audio_set_volume(volume)

    def update_ui(self):
        """ Updates the user interface. """

        # Set the slider's position to its corresponding media position
        # Note that the setValue function only takes values of type int,
        # so we must first convert the corresponding media position.
        media_pos = int(self.mediaplayer.get_position() * 1000)
        self.ui.horizontalSlider.setValue(media_pos)

        # update label_time
        msecs = self.mediaplayer.get_time()
        secs = int(msecs / 1000)
        mins = int(secs / 60)
        remainder_secs = str(secs - mins * 60)
        if len(remainder_secs) == 1:
            remainder_secs = "0" + remainder_secs
        self.ui.label_time.setText("Time: " + str(mins) + "." + str(remainder_secs))

        # No need to call this function if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.stop()

            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused:
                self.stop()

    def closeEvent(self, event):
        """ Stop the vlc player on close. """

        self.stop()
        if self.transcription is not None:
            cur = self.settings['conn'].cursor()
            text = self.ui.textEdit_transcription.toPlainText()
            cur.execute("update source set fulltext=? where id=?", [text, self.transcription[0]])
            self.settings['conn'].commit()






