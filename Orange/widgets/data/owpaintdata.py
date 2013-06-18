import copy
import math
import os
import random
from functools import partial

from PyQt4 import QtCore
from PyQt4 import QtGui
from Orange.widgets import widget, gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils import itemmodels
from Orange.widgets.utils.plot import owplot, owconstants, owpoint
from Orange.data.domain import Domain
from Orange.data.instance import Instance
from Orange.data.table import Table
from Orange.data.variable import DiscreteVariable, ContinuousVariable

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
icon_magnet = os.path.join(dir_path, "icons/paintdata/magnet.svg")
icon_jitter = os.path.join(dir_path, "icons/paintdata/jitter.svg")
icon_brush = os.path.join(dir_path, "icons/paintdata/brush.svg")
icon_put = os.path.join(dir_path, "icons/paintdata/put.svg")
icon_select = os.path.join(dir_path,
                           "icons/paintdata/select-transparent_42px.png")
#icon_lasso = os.path.join(dir_path,
#                          "icons/paintdata/lasso-transparent_42px.png")
icon_zoom = os.path.join(dir_path, "icons/paintdata/Dlg_zoom2.png")


class PaintDataPlot(owplot.OWPlot):
    def __init__(self, parent=None, name="None", show_legend=1, axes=None,
                 widget=None):
        super().__init__(parent, name, show_legend,
                         axes or [owconstants.xBottom, owconstants.yLeft],
                         widget)
        self.state = owconstants.NOTHING
        self.graph_margin = 10
        self.y_axis_extra_margin = -10
        self.animate_plot = False
        self.animate_points = False
        self.tool = None

    def mousePressEvent(self, event):
        if self.state == owconstants.NOTHING and self.tool:
            self.tool.mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.state == owconstants.NOTHING and self.tool:
            self.tool.mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.state == owconstants.NOTHING and self.tool:
            self.tool.mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)


class DataTool(QtCore.QObject):
    """
    A base class for data tools that operate on PaintDataPlot
    widget.

    """
    cursor = QtCore.Qt.ArrowCursor
    editingFinished = QtCore.pyqtSignal()

    class optionsWidget(QtGui.QFrame):
        """
        An options (parameters) widget for the tool (this will
        be put in the "Options" box in the main OWPaintData widget
        when this tool is selected.

        """
        def __init__(self, tool, parent=None):
            QtGui.QFrame.__init__(self, parent)
            self.tool = tool


    def __init__(self, parent):
        QtCore.QObject.__init__(self, parent)
        self.widget = parent
        self.widget.plot.setCursor(self.cursor)
        self.state = owconstants.NOTHING

    def mousePressEvent(self, event):
        return False

    def mouseMoveEvent(self, event):
        return False

    def mouseReleaseEvent(self, event):
        return False

    def toDataPoint(self, point):
        """
        Converts mouse position point to data point as its represented on the
        graph.
        """
        # first we convert it from widget point to scene point
        scenePoint = self.widget.plot.mapToScene(point)
        # and then from scene to data point
        return self.widget.plot.map_from_graph(scenePoint, zoom=True)

    def onToolSelection(self):
        self.widget.plot.state = self.state
        self.widget.plot.setCursor(self.cursor)


class PutInstanceTool(DataTool):
    cursor = QtCore.Qt.CrossCursor

    def mousePressEvent(self, event):
        dataPoint = self.toDataPoint(event.pos())
        if event.buttons() & QtCore.Qt.LeftButton:
            self.widget.addDataPoints([dataPoint])
            self.editingFinished.emit()
        return True


class BrushTool(DataTool):
    brushRadius = 70
    density = 5
    cursor = QtCore.Qt.CrossCursor

    class optionsWidget(QtGui.QFrame):
        def __init__(self, tool, parent=None):
            QtGui.QFrame.__init__(self, parent)
            self.tool = tool
            layout = QtGui.QFormLayout()
            self.radiusSlider = QtGui.QSlider(QtCore.Qt.Horizontal)
            self.radiusSlider.pyqtConfigure(minimum=50, maximum=100,
                                            value=self.tool.brushRadius)
            self.densitySlider = QtGui.QSlider(QtCore.Qt.Horizontal)
            self.densitySlider.pyqtConfigure(minimum=3, maximum=10,
                                             value=self.tool.density)

            layout.addRow("Radius", self.radiusSlider)
            layout.addRow("Density", self.densitySlider)
            self.setLayout(layout)

            self.radiusSlider.valueChanged.connect(
                partial(setattr, self.tool, "brushRadius"))
            self.densitySlider.valueChanged.connect(
                partial(setattr, self.tool, "density"))

    def mousePressEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            dataPoint = self.toDataPoint(event.pos())
            self.previousDataPoint = dataPoint
            self.widget.addDataPoints(self.createPoints(dataPoint))
        return True

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            dataPoint = self.toDataPoint(event.pos())
            if (abs(dataPoint[0] - self.previousDataPoint[0]) >
                    self.brushRadius / 2000 or
                    abs(dataPoint[1] - self.previousDataPoint[1]) >
                    self.brushRadius / 2000):
                self.widget.addDataPoints(self.createPoints(dataPoint))
                self.previousDataPoint = dataPoint
        return True

    def mouseReleaseEvent(self, event):
        if event.button() & QtCore.Qt.LeftButton:
            self.editingFinished.emit()
        return True

    def createPoints(self, point):
        """
        Creates random points around the point that is passed in.
        """
        points = []
        x, y = point
        radius = self.brushRadius / 1000
        for i in range(self.density):
            rndX = random.random() * radius
            rndY = random.random() * radius
            points.append((x + (radius / 2) - rndX, y + (radius / 2) - rndY))
        return points


class MagnetTool(BrushTool):
    def mousePressEvent(self, event):
        radius = self.brushRadius
        if event.buttons() & QtCore.Qt.LeftButton:
            dataPoint = self.toDataPoint(event.pos())
            self.widget.magnet(dataPoint, self.density, radius)
        return True

    def mouseMoveEvent(self, event):
        self.mousePressEvent(event)


class JitterTool(BrushTool):
    def mousePressEvent(self, event):
        radius = self.brushRadius
        if event.buttons() & QtCore.Qt.LeftButton:
            dataPoint = self.toDataPoint(event.pos())
            self.widget.jitter(dataPoint, self.density, radius)
        return True

    def mouseMoveEvent(self, event):
        self.mousePressEvent(event)


class SelectTool(DataTool):
    cursor = QtCore.Qt.ArrowCursor

    class optionsWidget(QtGui.QFrame):
        def __init__(self, tool, parent=None):
            QtGui.QFrame.__init__(self, parent)
            self.tool = tool
            layout = QtGui.QVBoxLayout()
            label = QtGui.QLabel('Select multiple times.')
            label2 = QtGui.QLabel('Right click deselect')
            delete = QtGui.QToolButton(self)
            delete.pyqtConfigure(text="Delete",
                                 toolTip="Delete selected instances")
            delete.setShortcut("Delete")
            delete.clicked.connect(self.tool.deleteSelected)
            layout.addWidget(label)
            layout.addWidget(label2)
            layout.addWidget(delete)
            layout.addStretch(10)
            self.setLayout(layout)

    def __init__(self, parent):
        super(SelectTool, self).__init__(parent)
        self.widget.plot.activate_selection()

    def deleteSelected(self):
        points = [point.coordinates()
                  for point in self.widget.plot.selected_points()]
        self.widget.delDataPoints(points)
        self.widget.plot.unselect_all_points()
        self.editingFinished.emit()

    def onToolSelection(self):
        self.widget.plot.activate_selection()
        self.widget.plot.setCursor(self.cursor)


class ZoomTool(DataTool):
    class optionsWidget(QtGui.QFrame):
        def __init__(self, tool, parent=None):
            QtGui.QFrame.__init__(self, parent)
            self.tool = tool
            layout = QtGui.QVBoxLayout()
            label = QtGui.QLabel('Left click zoom in.')
            label2 = QtGui.QLabel('Right click zoom out.')
            layout.addWidget(label)
            layout.addWidget(label2)
            layout.addStretch(10)
            self.setLayout(layout)

    def __init__(self, parent):
        super(ZoomTool, self).__init__(parent)
        self.state = owconstants.ZOOMING


class CommandAddData(QtGui.QUndoCommand):
    def __init__(self, data, points, classLabel, widget, description):
        super(CommandAddData, self).__init__(description)
        self.data = data
        self.points = points
        self.row = len(self.data)
        self.classLabel = classLabel
        self.widget = widget

    def redo(self):
        instances = [Instance(self.widget.data.domain,
                              [x, y, self.classLabel])
                     for x, y in self.points if 0 <= x <= 1 and 0 <= y <= 1]
        self.widget.data.extend(instances)
        self.widget.updatePlot()

    def undo(self):
        del self.widget.data[self.row:self.row + len(self.points)]
        self.widget.updatePlot()


class CommandDelData(QtGui.QUndoCommand):
    def __init__(self, data, selectedPoints, widget, description):
        super(CommandDelData, self).__init__(description)
        self.data = data
        self.points = selectedPoints
        self.widget = widget
        self.oldData = copy.deepcopy(self.data)

    def redo(self):
        attr1, attr2 = self.widget.attr1, self.widget.attr2
        selected = [i for i, ex in enumerate(self.data)
                    if (float(ex[attr1]), float(ex[attr2])) in self.points]
        for i in reversed(selected):
            del self.widget.data[i]
        self.widget.updatePlot()

    def undo(self):
        self.widget.data = self.oldData
        self.widget.updatePlot()


class CommandMagnet(QtGui.QUndoCommand):
    def __init__(self, data, point, density, radius, widget, description):
        super(CommandMagnet, self).__init__(description)
        self.data = data
        self.widget = widget
        self.density = density
        self.radius = radius
        self.point = point
        self.oldData = copy.deepcopy(self.data)

    def redo(self):
        x, y = self.point
        rx, ry = self.radius / 1000, self.radius / 1000
        for ex in self.widget.data:
            x1, y1 = float(ex[self.widget.attr1]), float(ex[self.widget.attr2])
            distsq = (x1 - x) ** 2 + (y1 - y) ** 2
            dist = math.sqrt(distsq)
            attraction = self.density / 100.0
            advance = 0.005
            dx = -(x1 - x) / dist * attraction / max(distsq, rx) * advance
            dy = -(y1 - y) / dist * attraction / max(distsq, ry) * advance
            ex[self.widget.attr1] = x1 + dx
            ex[self.widget.attr2] = y1 + dy
        self.widget.updatePlot()

    def undo(self):
        self.widget.data = self.oldData
        self.widget.updatePlot()


class CommandJitter(QtGui.QUndoCommand):
    def __init__(self, data, point, density, radius, widget, description):
        super(CommandJitter, self).__init__(description)
        self.data = data
        self.widget = widget
        self.density = density
        self.point = point
        self.radius = radius
        self.oldData = copy.deepcopy(self.data)

    def redo(self):
        x, y = self.point
        rx, ry = self.radius / 1000, self.radius / 1000
        for ex in self.widget.data:
            x1, y1 = float(ex[self.widget.attr1]), float(ex[self.widget.attr2])
            distsq = (x1 - x) ** 2 + (y1 - y) ** 2
            dist = math.sqrt(distsq)
            attraction = self.density / 100.0
            advance = 0.01
            dx = -(x1 - x) / dist * attraction / max(dist, rx) * advance
            dy = -(y1 - y) / dist * attraction / max(dist, ry) * advance
            ex[self.widget.attr1] = x1 - random.normalvariate(0, dx)
            ex[self.widget.attr2] = y1 - random.normalvariate(0, dy)
        self.widget.updatePlot()

    def undo(self):
        self.widget.data = self.oldData
        self.widget.updatePlot()


class CommandAddClassLabel(QtGui.QUndoCommand):
    def __init__(self, data, newClassLabel, classValuesModel, widget,
                 description):
        super(CommandAddClassLabel, self).__init__(description)
        self.data = data
        self.newClassLabel = newClassLabel
        self.oldDomain = data.domain
        self.classValuesModel = classValuesModel
        self.widget = widget
        self.newClassLabel = newClassLabel

    def redo(self):
        self.classValuesModel.append(self.newClassLabel)
        newdomain = Domain([ContinuousVariable(self.widget.attr1),
                            ContinuousVariable(self.widget.attr2)],
                           DiscreteVariable("Class",
                                            values=self.classValuesModel))
        newdata = Table(newdomain)
        instances = [Instance(newdomain,
                              [float(ex[a]) for a in ex.domain.attributes] +
                              [str(ex.get_class())]) for ex in self.data]

        newdata.extend(instances)
        self.widget.data = newdata
        self.widget.removeClassLabel.setEnabled(len(self.classValuesModel) > 1)
        self.widget.updatePlot()

    def undo(self):
        self.widget.data = self.data
        del self.classValuesModel[-1]
        self.widget.removeClassLabel.setEnabled(len(self.classValuesModel) > 1)
        self.widget.updatePlot()


class CommandRemoveClassLabel(QtGui.QUndoCommand):
    def __init__(self, data, classValuesModel, index, widget, description):
        super(CommandRemoveClassLabel, self).__init__(description)
        self.data = data
        self.classValuesModel = classValuesModel
        self.index = index
        self.widget = widget

    def redo(self):
        self.label = self.classValuesModel.pop(self.index)
        examples = [ex for ex in self.data
                    if str(ex.get_class()) != self.label]
        newdomain = Domain([ContinuousVariable(self.widget.attr1),
                            ContinuousVariable(self.widget.attr2)],
                           DiscreteVariable("Class",
                                            values=self.classValuesModel))
        newdata = Table(newdomain)
        for ex in examples:
            if str(ex.get_class()) != self.label and \
                    str(ex.get_class()) in self.classValuesModel:
                newdata.append(
                    Instance(newdomain,
                             [float(ex[a]) for a in ex.domain.attributes] +
                             [str(ex.get_class())]))

        self.widget.data = newdata
        self.widget.updatePlot()

    def undo(self):
        self.classValuesModel.insert(self.index, self.label)
        self.widget.data = self.data
        self.widget.removeClassLabel.setEnabled(len(self.classValuesModel) > 1)
        self.widget.updatePlot()


class CommandChangeLabelName(QtGui.QUndoCommand):
    def __init__(self, data, classValuesModel, index, widget, description):
        super(CommandChangeLabelName, self).__init__(description)
        self.data = data
        self.classValuesModel = classValuesModel
        self.changedLabel = classValuesModel[index]
        self.widget = widget
        self.index = index

    def redo(self):
        newdomain = Domain([ContinuousVariable(self.widget.attr1),
                            ContinuousVariable(self.widget.attr2)],
                           DiscreteVariable("Class",
                                            values=self.classValuesModel))
        newdata = Table(newdomain)
        for ex in self.data:
            print(ex.get_class())
            if str(ex.get_class()) not in self.classValuesModel:
                self.oldLabelName = str(ex.get_class())
                instance = Instance(
                    newdomain, [float(ex[a]) for a in ex.domain.attributes] +
                               [self.changedLabel])
                newdata.append(instance)
            else:
                newdata.append(
                    Instance(newdomain,
                             [float(ex[a]) for a in ex.domain.attributes] +
                             [str(ex.get_class())]))
        self.widget.data = newdata
        self.widget.updatePlot()

    def undo(self):
        self.classValuesModel[self.index] = self.oldLabelName
        self.widget.data = self.data
        self.widget.updatePlot()


class OWPaintData(widget.OWWidget):
    TOOLS = [("Brush", "Create multiple instances", BrushTool, icon_brush),
             ("Put", "Put individual instances", PutInstanceTool, icon_put),
             ("Select", "Select and move instances", SelectTool, icon_select),
             ("Jitter", "Jitter instances", JitterTool, icon_jitter),
             ("Magnet", "Attract multiple instances", MagnetTool, icon_magnet),
             ("Zoom", "Zoom", ZoomTool, icon_zoom)
             ]
    _name = "Paint Data"
    _description = """
    Creates the data by painting on the graph."""
    _long_description = """
    """
    _icon = "icons/PaintData.svg"
    _author = "Martin Frlin"
    _priority = 10
    _category = "Data"
    _keywords = ["data", "paint", "create"]
    outputs = [("Data", Table)]

    commit_on_change = Setting(False)
    attr1 = Setting("x")
    attr2 = Setting("y")

    def __init__(self, parent=None, signalManager=None, settings=None):
        super().__init__(parent, signalManager, settings)

        self.data = None

        self.undoStack = QtGui.QUndoStack(self)

        self.plot = PaintDataPlot(self.mainArea, "Painted Plot", widget=self)
        self.classValuesModel = itemmodels.PyListModel(
            ["Class-1", "Class-2"], self, flags=QtCore.Qt.ItemIsSelectable |
            QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
        self.classValuesModel.dataChanged.connect(self.classNameChange)
        self.data = Table(
            Domain([ContinuousVariable(self.attr1),
                    ContinuousVariable(self.attr2)],
                   DiscreteVariable("Class", values=self.classValuesModel)))

        self.toolsStackCache = {}

        self.initUI()
        self.initPlot()
        self.updatePlot()

    def initUI(self):
        namesBox = gui.widgetBox(self.controlArea, "Names")

        gui.lineEdit(namesBox, self, "attr1", "Variable X ",
                     controlWidth=80, orientation="horizontal",
                     enterPlaceholder=True, callback=self.commitIf)
        gui.lineEdit(namesBox, self, "attr2", "Variable Y ",
                     controlWidth=80, orientation="horizontal",
                     enterPlaceholder=True, callback=self.commitIf)
        gui.separator(namesBox)

        gui.widgetLabel(namesBox, "Class labels")
        self.classValuesView = listView = QtGui.QListView()
        listView.setSelectionMode(QtGui.QListView.SingleSelection)
        listView.setSizePolicy(QtGui.QSizePolicy.Ignored,
                               QtGui.QSizePolicy.Maximum)
        listView.setModel(self.classValuesModel)
        listView.selectionModel().select(
            self.classValuesModel.index(0),
            QtGui.QItemSelectionModel.ClearAndSelect)
        listView.setFixedHeight(80)
        namesBox.layout().addWidget(listView)

        addClassLabel = QtGui.QAction("+", self)
        addClassLabel.pyqtConfigure(toolTip="Add class label")
        addClassLabel.triggered.connect(self.addNewClassLabel)
        self.removeClassLabel = QtGui.QAction("-", self)
        self.removeClassLabel.pyqtConfigure(toolTip="Remove class label")
        self.removeClassLabel.triggered.connect(self.removeSelectedClassLabel)
        actionsWidget = itemmodels.ModelActionsWidget(
            [addClassLabel, self.removeClassLabel], self)
        actionsWidget.layout().addStretch(10)
        actionsWidget.layout().setSpacing(1)
        namesBox.layout().addWidget(actionsWidget)

        toolsBox = gui.widgetBox(self.controlArea, "Tools",
                                 orientation=QtGui.QGridLayout(),
                                 addSpace=True)
        self.toolActions = QtGui.QActionGroup(self)
        self.toolActions.setExclusive(True)

        for i, (name, tooltip, tool, icon) in enumerate(self.TOOLS):
            action = QtGui.QAction(name, self)
            action.setToolTip(tooltip)
            action.setCheckable(True)
            action.setIcon(QtGui.QIcon(icon))
            # using the old connect here due to problems with overloading
            self.connect(action, QtCore.SIGNAL("triggered()"),
                         lambda tool=tool: self.setCurrentTool(tool))
            button = QtGui.QToolButton()
            button.setDefaultAction(action)
            button.setIconSize(QtCore.QSize(24, 24))
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            button.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                 QtGui.QSizePolicy.Fixed)
            toolsBox.layout().addWidget(button, i / 3, i % 3)
            self.toolActions.addAction(action)

        for column in range(3):
            toolsBox.layout().setColumnMinimumWidth(column, 10)
            toolsBox.layout().setColumnStretch(column, 1)

        self.optionsLayout = QtGui.QStackedLayout()
        optionsBox = gui.widgetBox(self.controlArea, "Options", addSpace=True,
                                   orientation=self.optionsLayout)

        undoRedoBox = gui.widgetBox(self.controlArea, "", addSpace=True)
        undo = QtGui.QAction("Undo", self)
        undo.pyqtConfigure(toolTip="Undo Action (Ctrl+Z)")
        undo.setShortcut("Ctrl+Z")
        undo.triggered.connect(self.undoStack.undo)
        redo = QtGui.QAction("Redo", self)
        redo.pyqtConfigure(toolTip="Redo Action (Ctrl+Shift+Z)")
        redo.setShortcut("Ctrl+Shift+Z")
        redo.triggered.connect(self.undoStack.redo)
        undoRedoActionsWidget = itemmodels.ModelActionsWidget(
            [undo, redo], self)
        undoRedoActionsWidget.layout().addStretch(10)
        undoRedoActionsWidget.layout().setSpacing(1)
        undoRedoBox.layout().addWidget(undoRedoActionsWidget)

        commitBox = gui.widgetBox(self.controlArea, "Commit")
        gui.checkBox(commitBox, self, "commit_on_change", "Commit on change",
                     tooltip="Send the data on any change.")
        gui.button(commitBox, self, "Commit", callback=self.sendData)

        # main area GUI
        self.mainArea.layout().addWidget(self.plot)

    def initPlot(self):
        self.plot.set_axis_title(owconstants.xBottom, self.data.domain[0].name)
        self.plot.set_axis_title(owconstants.yLeft, self.data.domain[1].name)
        self.plot.set_axis_scale(owconstants.xBottom, 0, 1, 0.1)
        self.plot.set_axis_scale(owconstants.yLeft, 0, 1, 0.1)
        self.updatePlot()

    def updatePlot(self):
        self.plot.legend().clear()
        colorDict = {}
        for i, value in enumerate(self.data.domain[2].values):
            rgb = self.plot.discrete_palette.getRGB(i)
            color = QtGui.QColor(*rgb)
            colorDict[i] = color
            self.plot.legend().add_item(
                self.data.domain[2].name, value,
                owpoint.OWPoint(owpoint.OWPoint.Diamond, color, 5))
        c_data = [colorDict[int(value)] for value in self.data.Y[:, 0]]
        self.plot.set_main_curve_data(
            list(self.data.X[:, 0]), list(self.data.X[:, 1]),
            color_data=c_data, label_data=[], size_data=[5],
            shape_data=[owpoint.OWPoint.Diamond])
        self.plot.replot()

    def addNewClassLabel(self):
        i = 1
        newlabel = ""  # For PyCharm
        while True:
            newlabel = "Class-%i" % i
            if newlabel not in self.classValuesModel:
                break
            i += 1
        command = CommandAddClassLabel(self.data, newlabel,
                                       self.classValuesModel, self,
                                       "Add Label")
        self.undoStack.push(command)

        newindex = self.classValuesModel.index(len(self.classValuesModel) - 1)
        self.classValuesView.selectionModel().select(
            newindex, QtGui.QItemSelectionModel.ClearAndSelect)
        self.removeClassLabel.setEnabled(len(self.classValuesModel) > 1)

    def removeSelectedClassLabel(self):
        index = self.selectedClassLabelIndex()
        if index is not None:
            command = CommandRemoveClassLabel(self.data, self.classValuesModel,
                                              index, self, "Remove Label")
            self.undoStack.push(command)

        newindex = self.classValuesModel.index(max(0, index - 1))
        self.classValuesView.selectionModel().select(
            newindex, QtGui.QItemSelectionModel.ClearAndSelect)
        self.removeClassLabel.setEnabled(len(self.classValuesModel) > 1)

    def classNameChange(self, index, _):
        command = CommandChangeLabelName(self.data, self.classValuesModel,
                                         index.row(), self, "Label Change")
        self.undoStack.push(command)

    def selectedClassLabelIndex(self):
        rows = [i.row()
                for i in self.classValuesView.selectionModel().selectedRows()]
        if rows:
            return rows[0]
        else:
            return None

    def setCurrentTool(self, tool):
        if tool not in self.toolsStackCache:
            newtool = tool(self)
            option = newtool.optionsWidget(newtool, self)
            self.optionsLayout.addWidget(option)
            newtool.editingFinished.connect(self.commitIf)
            self.toolsStackCache[tool] = (newtool, option)

        self.currentTool, self.currentOptionsWidget = tool, option = \
            self.toolsStackCache[tool]
        self.plot.tool = tool
        tool.onToolSelection()
        self.optionsLayout.setCurrentWidget(option)

    def addDataPoints(self, points):
        command = CommandAddData(
            self.data, points,
            self.classValuesModel[self.selectedClassLabelIndex()], self,
            "Add Data")
        self.undoStack.push(command)

    def delDataPoints(self, points):
        if points:
            command = CommandDelData(self.data, points, self, "Delete Data")
            self.undoStack.push(command)

    def magnet(self, point, density, radius):
        command = CommandMagnet(self.data, point, density, radius, self,
                                "Magnet")
        self.undoStack.push(command)

    def jitter(self, point, density, radius):
        command = CommandJitter(self.data, point, density, radius, self,
                                "Jitter")
        self.undoStack.push(command)

    def commitIf(self):
        if self.commit_on_change:
            self.sendData()

    def sendData(self):
        data = self.data
        values = set([str(ex.get_class()) for ex in data])
        if len(values) == 1:
            # Remove the useless class variable.
            domain = Domain(data.domain.attributes, None)
            data = Table(domain, data)
        self.send("Data", data)

    def sizeHint(self):
        return QtCore.QSize(1200, 800)


if __name__ == "__main__":
    a = QtGui.QApplication([])
    ow = OWPaintData()
    ow.show()
    a.exec_()
    ow.saveSettings()