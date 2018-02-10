from __future__ import division, print_function
import numpy as np
import traceback
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, Ellipse

DIR_X0 = 1
DIR_Y0 = 2
DIR_X1 = 4
DIR_Y1 = 8


class FigureDragger:
    last_picked = False
    active_object = None
    drag_object = None
    fig = None
    first_resize = True
    displaying = False
    snaps = None

    changes = None

    def __init__(self, fig, xsnaps=None, ysnaps=None, unit="cm"):
        self.fig = fig
        # store dragger, so that it is not eaten by the garbage collector
        fig.figure_dragger = self
        self.grabbers = []
        self.edits = []
        self.last_edit = -1
        self.changes = {}

        # make all the subplots pickable
        for index, axes in enumerate(self.fig.axes):
            #axes.set_title(index)
            axes.number = index
            axes.set_picker(True)
            leg = axes.get_legend()
            if leg:
                dragger = DraggableLegend(leg, use_blit=True)
                leg._draggable = dragger
            for text in axes.texts:
                dragger = DraggableText(text, use_blit=True)
                text._draggable = dragger

            dragger = DraggableAxes(axes, use_blit=True)
            axes._draggable = dragger
        for text in self.fig.texts:
            dragger = DraggableText(text, use_blit=True)
            text._draggable = dragger

        # store the position where StartPylustration was called
        self.stack_position = traceback.extract_stack()[-3]

        self.fig_inch_size = fig.get_size_inches()

        """
        self.snaps = []
        if xsnaps is not None:
            for x in xsnaps:
                if unit == "cm":
                    x = x / 2.54 / fig.get_size_inches()[0]
                if x < 0:
                    x = 1 + x
                plt.plot([x, x], [0, 1], '-', color=[0.8, 0.8, 0.8], transform=fig.transFigure, clip_on=False, lw=1,
                         zorder=-10)
                self.snaps.append(Snap(x, None, [x, x], [0, 1]))
        if ysnaps is not None:
            for y in ysnaps:
                if unit == "cm":
                    y = y / 2.54 / fig.get_size_inches()[1]
                if y < 0:
                    y = 1 + y
                plt.plot([0, 1], [y, y], '-', color=[0.8, 0.8, 0.8], transform=fig.transFigure, clip_on=False, lw=1,
                         zorder=-10)
                self.snaps.append(Snap(None, y, [0, 1], [y, y]))
        """
        # add a text showing the figure size
        self.text = plt.text(0, 0, "", transform=self.fig.transFigure, clip_on=False, zorder=100)

        # connect event callbacks
        #fig.canvas.mpl_connect("pick_event", self.on_pick_event)
        fig.canvas.mpl_connect('button_press_event', self.button_press_event)
        #fig.canvas.mpl_connect('motion_notify_event', self.mouse_move_event)
        fig.canvas.mpl_connect('button_release_event', self.button_release_event)
        fig.canvas.mpl_connect('key_press_event', self.key_press_event)
        #fig.canvas.mpl_connect('draw_event', self.draw_event)
        fig.canvas.mpl_connect('resize_event', self.resize_event)
        #fig.canvas.mpl_connect('scroll_event', self.scroll_event)

        self.selected_element = None
        self.grab_element = None

    def get_picked_element(self, event, element=None, picked_element=None):
        # start with the figure
        if element is None:
            element = self.fig
        # iterate over all children
        for child in sorted(element.get_children(), key=lambda x: x.get_zorder()):
            # check if the element is contained in the event and has an active dragger
            if child.contains(event)[0] and ((getattr(child, "_draggable", None) and getattr(child, "_draggable",
                                                                                           None).connected) or isinstance(child, Grabber)):
                # use this element as the current best matching element
                picked_element = child
            # iterate over the children's children
            picked_element = self.get_picked_element(event, child, picked_element)
        return picked_element

    def button_release_event(self, event):
        # release the grabber
        if self.grab_element:
            self.grab_element.button_release_event(event)
            self.grab_element = None
        # or notify the selected element
        elif self.selected_element:
            self.selected_element._draggable.button_release_event(event)

    def button_press_event(self, event):
        # recursively iterate over all elements
        picked_element = self.get_picked_element(event)

        # if the element is a grabber, store it
        if isinstance(picked_element, Grabber):
            self.grab_element = picked_element
        # if not, we want to keep our selected element, if the click was in the area of the selected element
        elif self.selected_element is None or not self.selected_element.contains(event)[0]:
                self.select_element(picked_element)

        # if we have a grabber, notify it
        if self.grab_element:
            self.grab_element.button_press_event(event)
        # if not, notify the selected element
        elif self.selected_element and self.selected_element.contains(event)[0]:
            self.selected_element._draggable.button_press_event(event)

    def select_element(self, element, event=None):
        # do nothing if it is already selected
        if element == self.selected_element:
            return
        # if there was was previously selected element, deselect it
        if self.selected_element is not None:
            self.selected_element._draggable.on_deselect(event)
            self.selected_element = None

        # if there is a new element, select it
        if element is not None:
            element._draggable.on_select(event)
            self.selected_element = element

    def addChange(self, change_key, change):
        self.changes[change_key] = change
        print(self.changes)

    def addEdit(self, edit):
        if self.last_edit < len(self.edits)-1:
            self.edits = self.edits[:self.last_edit+1]
        self.edits.append(edit)
        self.last_edit = len(self.edits)-1

    def backEdit(self):
        if self.last_edit < 0:
            return
        edit = self.edits[self.last_edit]
        edit[0]()
        self.last_edit -= 1
        self.fig.canvas.draw()

    def forwardEdit(self):
        if self.last_edit >= len(self.edits)-1:
            return
        edit = self.edits[self.last_edit+1]
        edit[1]()
        self.last_edit += 1
        self.fig.canvas.draw()

    def draw(self):
        # only draw if the canvas is not already drawing
        if not self.displaying:
            # store the drawing state
            self.displaying = True
            # remove events
            self.fig.canvas.flush_events()
            # draw the canvas
            self.fig.canvas.draw()

    def draw_event(self, event):
        # set the drawing state back to false
        self.displaying = False

    def key_press_event(self, event):
        # space: print code to restore current configuration
        if event.key == ' ':
            figure = "fig = plt.figure(%s)\n" % self.fig.number
            block = getTextFromFile(figure, self.stack_position).split("\n")
            output = "#% start: automatic generated code from pylustration\n"
            output += figure
            for line in block[1:]:
                line = line.strip()
                if line == "":
                    continue
                for key in self.changes:
                    if line.startswith(key):
                        break
                else:
                    output += line + "\n"
            for key in self.changes:
                output += self.changes[key] + "\n"
            output += "#% end: automatic generated code from pylustration"
            print(output)
            insertTextToFile(output, self.stack_position)
        if event.key == "ctrl+z":
            self.backEdit()
        if event.key == "ctrl+y":
            self.forwardEdit()

    def resize_event(self, event):
        # on the first resize (when the figure window plops up) store the additional size (edit toolbar and stuff)
        if self.first_resize:
            self.first_resize = False
            # store the offset of the figuresize
            self.inch_offset = np.array(self.fig.get_size_inches()) - np.array(self.fig_inch_size)
        # draw the text with the figure size
        offx, offy = self.fig.transFigure.inverted().transform([5, 5])
        self.text.set_position([offx, offy])
        self.text.set_text("%.2f x %.2f cm" % (
            (self.fig.get_size_inches()[0] - self.inch_offset[0]) * 2.54,
            (self.fig.get_size_inches()[1] - self.inch_offset[1]) * 2.54))

    def scroll_event(self, event):
        inches = np.array(self.fig.get_size_inches()) - self.inch_offset
        old_dpi = self.fig.get_dpi()
        new_dpi = self.fig.get_dpi() + 10 * event.step
        self.inch_offset /= old_dpi / new_dpi
        self.fig.set_dpi(self.fig.get_dpi() + 10 * event.step)
        self.fig.canvas.draw()
        self.fig.set_size_inches(inches + self.inch_offset, forward=True)
        print(self.fig_inch_size, self.fig.get_size_inches())
        self.resize_event(None)
        print(self.fig_inch_size, self.fig.get_size_inches())
        print("---")
        self.draw()
        print(self.fig_inch_size, self.fig.get_size_inches())
        self.resize_event(None)
        print(self.fig_inch_size, self.fig.get_size_inches())
        print("###")


def moveArtist(index, x1, y1, x2, y2):
    positions = []
    artists = []
    for index2, artist in enumerate(plt.gcf().axes[index].get_children()):
        if artist.pickable():
            try:
                positions.append(artist.original_pos)
            except:
                positions.append(artist.get_position())
            artists.append(artist)
    distance = np.linalg.norm(np.array([x1, y1]) - np.array(positions), axis=1)
    print(np.min(distance), np.array([x2, y2]), np.array(positions).shape)
    index = np.argmin(distance)
    try:
        artists[index].original_pos
    except:
        artists[index].original_pos = [x1, y1]
    print("########", artist)
    artists[index].set_position([x2, y2])

def getTextFromFile(marker, stack_pos):
    block_active = False
    block = ""
    last_block = -10
    written = False
    with open(stack_pos.filename, 'r') as fp1:
        for lineno, line in enumerate(fp1):
            if block_active:
                if line.strip().startswith("#% end:"):
                    block_active = False
                    last_block = lineno
                    if block.split("\n", 1)[0] == marker[:-1]:
                        break
                    block = ""
                block = block + line
            elif line.strip().startswith("#% start:"):
                #block = block + line
                block_active = True
            if block_active:
                continue
    return block


def insertTextToFile(text, stack_pos):
    block_active = False
    block = ""
    last_block = -10
    written = False
    with open(stack_pos.filename + ".tmp", 'w') as fp2:
        with open(stack_pos.filename, 'r') as fp1:
            for lineno, line in enumerate(fp1):
                if block_active:
                    block = block + line
                    if line.strip().startswith("#% end:"):
                        block_active = False
                        last_block = lineno
                        continue
                elif line.strip().startswith("#% start:"):
                    block = block + line
                    block_active = True
                if block_active:
                    continue
                # print(lineno, stack_pos.lineno, last_block)
                if not written and (lineno == stack_pos.lineno - 1 or last_block == lineno - 1):
                    for i in range(len(line)):
                        if line[i] != " " and line[i] != "\t":
                            break
                    indent = line[:i]
                    for line_text in text.split("\n"):
                        fp2.write(indent + line_text + "\n")
                    written = True
                    last_block = -10
                    block = ""
                elif last_block == lineno - 1:
                    fp2.write(block)
                fp2.write(line)

    with open(stack_pos.filename + ".tmp", 'r') as fp2:
        with open(stack_pos.filename, 'w') as fp1:
            for line in fp2:
                fp1.write(line)
    print("Save to", stack_pos.filename, "line", stack_pos.lineno)


class snapBase(Line2D):
    def __init__(self, ax_source, ax_target, edge):
        self.ax_source = ax_source
        self.ax_target = ax_target
        self.edge = edge
        Line2D.__init__(self, [], [], transform=None, clip_on=False, lw=1, zorder=100, linestyle="dashed",
                        color="r", marker="o", ms=1)
        plt.gca().add_artist(self)

    def getPosition(self, axes):
        return np.array(axes.figure.transFigure.transform(axes.get_position())).flatten()

    def getDistance(self, p1):
        pass

    def checkSnap(self, index):
        distance = self.getDistance(index)
        if abs(distance) < 10:
            return distance
        return None

    def checkSnapActive(self):
        distance = min([self.getDistance(index) for index in [0, 1]])
        if abs(distance) < 1:
            self.show()
        else:
            self.hide()

    def show(self):
        pass

    def hide(self):
        self.set_data((), ())

    def remove(self):
        self.hide()
        try:
            self.axes.artists.remove(self)
        except ValueError:
            pass

class snapSameEdge(snapBase):

    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return p1[self.edge] - p2[self.edge]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        if self.edge % 2 == 0:
            self.set_data((p1[self.edge], p1[self.edge], p2[self.edge], p2[self.edge]), (p1[self.edge-1], p1[self.edge+1], p2[self.edge-1], p2[self.edge+1]))
        else:
            self.set_data((p1[self.edge-1], p1[self.edge-3], p2[self.edge-1], p2[self.edge-3]), (p1[self.edge], p1[self.edge], p2[self.edge], p2[self.edge]))


class snapSameDimension(snapBase):
    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return (p2[self.edge-2]-p2[self.edge]) - (p1[self.edge-2]-p1[self.edge])

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        if self.edge % 2 == 0:
            self.set_data((p1[0], p1[2], np.nan, p2[0], p2[2]),
                          (p1[1] * 0.5 + p1[3] * 0.5, p1[1] * 0.5 + p1[3] * 0.5, np.nan, p2[1] * 0.5 + p2[3] * 0.5,
                           p2[1] * 0.5 + p2[3] * 0.5))
        else:
            self.set_data((p1[0] * 0.5 + p1[2] * 0.5, p1[0] * 0.5 + p1[2] * 0.5, np.nan, p2[0] * 0.5 + p2[2] * 0.5,
                           p2[0] * 0.5 + p2[2] * 0.5),
                          (p1[1], p1[3], np.nan, p2[1], p2[3]))


class snapSamePos(snapBase):
    def getPosition(self, text):
        return np.array(text.get_transform().transform(text.get_position()))

    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return p1[self.edge] - p2[self.edge]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        self.set_data((p1[0], p2[0]), (p1[1], p2[1]))


class snapSameBorder(snapBase):
    def overlap(self, p1, p2, dir):
        if p1[dir + 2] < p2[dir] or p1[dir] > p2[dir + 2]:
            return False
        return True

    def getBorders(self, p1, p2):
        borders = []
        for edge in [0, 1]:
            if self.overlap(p1, p2, 1-edge):
                if p1[edge + 2] < p2[edge]:
                    dist = p2[edge] - p1[edge + 2]
                    borders.append([edge*2+0, dist])
                if p1[edge] > p2[edge + 2]:
                    dist = p1[edge] - p2[edge + 2]
                    borders.append([edge*2+1, dist])
        return np.array(borders)

    def getDistance(self, index):
        self.ax_target2 = self.edge
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        p3 = self.getPosition(self.ax_target2)
        for edge in [index]:
            if (p1[edge+2] < p2[edge] or p1[edge] > p2[edge+2]) and self.overlap(p1, p2, 1-edge):
                distances = np.array([p2[edge]-p1[edge + 2], p1[edge] - p2[edge + 2]])
                index1 = np.argmax(distances)
                distance = distances[index1]
                borders = self.getBorders(p2, p3)
                if len(borders):
                    deltas = distance - borders[:, 1]
                    index2 = np.argmin(np.abs(deltas))
                    self.dir2 = borders[index2, 0]
                    self.dir1 = edge*2+index1
                    return deltas[index2]*(-1+2*index1)
        return np.inf

    def getConnection(self, p1, p2, dir):
        edge, order = dir//2, dir%2
        if order == 1:
            p1, p2 = p2, p1
        if edge == 0:
            y = np.mean([max(p1[1], p2[1]), min(p1[3], p2[3])])
            return [[p1[2], p2[0], np.nan], [y, y, np.nan]]
        x = np.mean([max(p1[0], p2[0]), min(p1[2], p2[2])])
        return [[x, x, np.nan], [p1[3], p2[1], np.nan]]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        p3 = self.getPosition(self.edge)
        x1, y1 = self.getConnection(p1, p2, self.dir1)
        x2, y2 = self.getConnection(p2, p3, self.dir2)
        x1.extend(x2)
        y1.extend(y2)
        self.set_data((x1, y1))



def checkSnaps(snaps):
    result = [0, 0]
    for index in range(2):
        best = np.inf
        for snap in snaps:
            delta = snap.checkSnap(index)
            if delta is not None and abs(delta) < abs(best):
                best = delta
        if best < np.inf:
            result[index] = best
    return result

def checkSnapsActive(snaps):
    for snap in snaps:
        snap.checkSnapActive()

def getSnaps(target, dir, no_height=False):
    snaps = []
    for index, axes in enumerate(target.figure.axes):
        if axes != target:
            # axes edged
            if dir & DIR_X0:
                snaps.append(snapSameEdge(target, axes, 0))
            if dir & DIR_Y0:
                snaps.append(snapSameEdge(target, axes, 1))
            if dir & DIR_X1:
                snaps.append(snapSameEdge(target, axes, 2))
            if dir & DIR_Y1:
                snaps.append(snapSameEdge(target, axes, 3))

            # snap same dimensions
            if not no_height:
                if dir & DIR_X0:
                    snaps.append(snapSameDimension(target, axes, 0))
                if dir & DIR_X1:
                    snaps.append(snapSameDimension(target, axes, 2))
                if dir & DIR_Y0:
                    snaps.append(snapSameDimension(target, axes, 1))
                if dir & DIR_Y1:
                    snaps.append(snapSameDimension(target, axes, 3))

            for axes2 in target.figure.axes:
                if axes2 != axes and axes2 != target:
                    snaps.append(snapSameBorder(target, axes, axes2))
    return snaps


class Grabber(object):
    fig = None
    target = None
    dir = None
    snaps = None
    moved = False

    got_artist = False

    def __init__(self, parent, x, y, artist, dir):
        self.parent = parent
        self.axes_pos = (x, y)
        self.fig = artist.figure
        self.target = artist
        self.dir = dir
        self.snaps = []
        self.updatePos()
        pos = self.target.get_position()
        self.aspect = pos.width / pos.height
        self.height = pos.height
        self.width = pos.width
        self.fix_aspect = self.target.get_aspect() != "auto" and self.target.get_adjustable() != "datalim"

        #c2 = self.fig.canvas.mpl_connect('pick_event', self.on_pick)
        #c3 = self.fig.canvas.mpl_connect('button_release_event', self.on_release)

        #self.cids = [c2, c3]

    def on_motion(self, evt):
        if self.got_artist:
            if self.parent.blit_initialized is False:
                self.parent.initBlit()

            self.movedEvent(evt)
            self.moved = True

            self.parent.doBlit()

    def button_press_event(self, evt):
        self.got_artist = True
        self.moved = False

        self._c1 = self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.clickedEvent(evt)

    def button_release_event(self, event):
        print("release Event", event)
        if self.got_artist:
            self.got_artist = False
            self.fig.canvas.mpl_disconnect(self._c1)
            self.releasedEvent(event)
            if self.parent.blit_initialized:
                self.parent.finishBlit()
            print("release")

    def get_xy(self):
        return self.center

    def set_xy(self, xy):
        self.center = xy

    def getPos(self):
        x, y = self.get_xy()
        return self.fig.transFigure.inverted().transform((x, y))

    def updatePos(self):
        x, y = self.target.transAxes.transform(self.axes_pos)
        self.set_xy((x, y))

    def clickedEvent(self, event):
        self.snaps = []
        #self.snaps.extend(self.parent.snaps)
        self.snap_index_offset = 0#len(self.snaps)
        self.snaps.extend(getSnaps(self.target, self.dir))

        self.mouse_x = event.x
        self.mouse_y = event.y

        self.old_pos = self.target.get_position()
        self.ox, self.oy = self.get_xy()

        pos = self.target.get_position()
        self.w, self.h = self.target.figure.transFigure.transform((pos.width, pos.height))

    def releasedEvent(self, event):
        pos = self.target.get_position()
        if self.moved:
            self.target.figure.figure_dragger.addEdit([lambda pos=self.old_pos: self.parent.redoPos(pos), lambda pos=pos: self.parent.redoPos(pos)])
            key = "fig.axes[%d].set_position" % self.target.number
            self.target.figure.figure_dragger.addChange(key, key + "([%f, %f, %f, %f])" % (pos.x0, pos.y0, pos.width, pos.height))
        for snap in self.snaps[self.snap_index_offset:]:
            snap.remove()
        self.snaps = self.snaps[self.snap_index_offset:]
        print("releasedEvent")

    def applyOffset(self, pos, event):
        self.set_xy((self.ox+pos[0], self.oy+pos[1]))
        x, y = self.getPos()
        axes = self.target
        pos = axes.get_position()
        modifier = "control" in event.key.split("+") if event.key is not None else False
        if self.dir & DIR_X0:
            pos.x0 = x
        if self.dir & DIR_Y0:
            pos.y0 = y
        if self.dir & DIR_X1:
            pos.x1 = x
        if self.dir & DIR_Y1:
            pos.y1 = y

        if self.fix_aspect or modifier:
            if self.dir & DIR_Y0 and not self.dir & DIR_X1 or (self.dir & DIR_X0 and self.dir & DIR_Y1):
                pos.x0 = pos.x1 - pos.height * self.aspect
            if self.dir & DIR_Y1 and not self.dir & DIR_X0:
                pos.x1 = pos.x0 + pos.height * self.aspect
            if self.dir & DIR_X0 and not self.dir & DIR_Y1 or (self.dir & DIR_X1 and self.dir & DIR_Y0):
                pos.y0 = pos.y1 - pos.width / self.aspect
            if self.dir & DIR_X1 and not self.dir & DIR_Y0:
                pos.y1 = pos.y0 + pos.width / self.aspect

        axes.set_position(pos)

        pos = self.target.get_position()
        self.w, self.h = self.target.figure.transFigure.transform((pos.width, pos.height))

    def movedEvent(self, event):
        dx = event.x - self.mouse_x
        dy = event.y - self.mouse_y

        self.applyOffset((dx, dy), event)

        if not ("shift" in event.key.split("+") if event.key is not None else False):
            offx, offy = checkSnaps(self.snaps)
            self.applyOffset((dx - offx, dy - offy), event)

        checkSnapsActive(self.snaps)
        self.parent.updateGrabbers()

    def keyPressEvent(self, event):
        pass


class GrabberRound(Ellipse, Grabber):
    d = 10

    def __init__(self, parent, x, y, artist, dir):
        Grabber.__init__(self, parent, x, y, artist, dir)
        Ellipse.__init__(self, (0, 0), self.d, self.d, picker=True, figure=artist.figure, edgecolor="k", zorder=1000)
        self.fig.patches.append(self)
        self.updatePos()


class GrabberRectangle(Rectangle, Grabber):
    d = 10

    def __init__(self, parent, x, y, artist, dir):
        Rectangle.__init__(self, (0, 0), self.d, self.d, picker=True, figure=artist.figure, edgecolor="k", zorder=1000)
        Grabber.__init__(self, parent, x, y, artist, dir)
        self.fig.patches.append(self)
        self.updatePos()

    def get_xy(self):
        xy = Rectangle.get_xy(self)
        return xy[0] + self.d / 2, xy[1] + self.d / 2

    def set_xy(self, xy):
        Rectangle.set_xy(self, (xy[0] - self.d / 2, xy[1] - self.d / 2))



from matplotlib.offsetbox import DraggableBase
from matplotlib.transforms import BboxTransformFrom

def on_pick_wrap(func):
    def on_pick(self, evt):
        func(self, evt)
        if evt.artist != self.ref_artist:
            self.on_release(evt)
    return on_pick

DraggableBase.on_pick = on_pick_wrap(DraggableBase.on_pick)

class DraggableBase(object):
    selected = False
    blit_initialized = False
    moved = False
    connected = False

    def __init__(self, ref_artist, use_blit=False):
        self.ref_artist = ref_artist
        self.got_artist = False

        self.canvas = self.ref_artist.figure.canvas
        self._use_blit = use_blit and self.canvas.supports_blit

        self.connect()

        self.grabbers = []
        self.snaps = []

    def connect(self):
        #c2 = self.canvas.mpl_connect('pick_event', self.on_pick)
        #c3 = self.canvas.mpl_connect('button_release_event', self.on_release)
        #self.cids = [c3]
        self.connected = True
        #self.ref_artist.set_picker(self.artist_picker)

    def initBlit(self):
        self.blit_initialized = True

        self.ref_artist.set_animated(True)
        for grabber in self.grabbers:
            grabber.set_animated(True)
            for snap in grabber.snaps:
                snap.set_animated(True)
        for snap in self.snaps:
            snap.set_animated(True)

        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.ref_artist.figure.bbox)

    def finishBlit(self):
        self.blit_initialized = False
        self.ref_artist.set_animated(False)
        for grabber in self.grabbers:
            grabber.set_animated(False)
            for snap in grabber.snaps:
                snap.hide()
                snap.set_animated(False)
        self.canvas.draw()

    def doBlit(self):
        self.canvas.restore_region(self.background)
        self.ref_artist.draw(self.ref_artist.figure._cachedRenderer)
        for grabber in self.grabbers:
            grabber.draw(self.ref_artist.figure._cachedRenderer)
            for snap in grabber.snaps:
                snap.draw(self.ref_artist.figure._cachedRenderer)
        for snap in self.snaps:
            snap.draw(self.ref_artist.figure._cachedRenderer)
        self.canvas.blit(self.ref_artist.figure.bbox)

    def on_motion(self, evt):
        if self.got_artist:
            dx = evt.x - self.mouse_x
            dy = evt.y - self.mouse_y
            self.update_offset(dx, dy, evt)
            self.moved = True
            self.canvas.draw()

    def on_motion_blit(self, evt):
        if self.got_artist:
            if self.blit_initialized is False:
                self.initBlit()

            dx = evt.x - self.mouse_x
            dy = evt.y - self.mouse_y
            self.update_offset(dx, dy, evt)
            self.moved = True
            self.doBlit()

    def on_select(self, evt):
        pass

    def on_deselect(self, evt):
        pass

    def button_press_event(self, evt):
        self.mouse_x, self.mouse_y = evt.x, evt.y
        self.got_artist = True
        self.moved = False

        if self._use_blit:
            self._c1 = self.canvas.mpl_connect('motion_notify_event', self.on_motion_blit)
        else:
            self._c1 = self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.save_offset()

    def button_release_event(self, event):
        if self.got_artist:
            if self.moved:
                self.finalize_offset()
            self.got_artist = False
            self.canvas.mpl_disconnect(self._c1)

        if self._use_blit and self.blit_initialized:
            self.finishBlit()

    def disconnect(self):
        """disconnect the callbacks"""
        #for cid in self.cids:
        #    self.canvas.mpl_disconnect(cid)
        self.connected = False
        self.ref_artist.set_picker(None)

    def artist_picker(self, artist, evt):
        return self.ref_artist.contains(evt)

    def save_offset(self):
        pass

    def update_offset(self, dx, dy, event):
        pass

    def finalize_offset(self):
        pass

class DraggableAxes(DraggableBase):

    def __init__(self, axes, use_blit=False):
        DraggableBase.__init__(self, axes, use_blit=use_blit)
        self.axes = axes
        #self.cids.append(self.canvas.mpl_connect('key_press_event', self.keyPressEvent))

    def addGrabber(self, x, y, artist, dir, GrabberClass):
        # add a grabber object at the given coordinates
        self.grabbers.append(GrabberClass(self, x, y, artist, dir))

    def updateGrabbers(self):
        for grabber in self.grabbers:
            grabber.updatePos()

    def on_deselect(self, evt):
        # remove all grabbers when an artist is deselected
        for grabber in self.grabbers[::-1]:
            # remove the grabber from the list
            self.grabbers.remove(grabber)
            # and from the figure (if it is drawn on the figure)
            try:
                self.axes.figure.patches.remove(grabber)
            except ValueError:
                pass
        self.axes.figure.canvas.draw()
        self.selected = False

    def on_select(self, evt):
        if self.selected:
            return
        self.selected = True

        self.addGrabber(0, 0, self.axes, DIR_X0 | DIR_Y0, GrabberRound)
        self.addGrabber(0.5, 0, self.axes, DIR_Y0, GrabberRectangle)
        self.addGrabber(1, 1, self.axes, DIR_X1 | DIR_Y1, GrabberRound)
        self.addGrabber(1, 0.5, self.axes, DIR_X1, GrabberRectangle)
        self.addGrabber(0, 1, self.axes, DIR_X0 | DIR_Y1, GrabberRound)
        self.addGrabber(0.5, 1, self.axes, DIR_Y1, GrabberRectangle)
        self.addGrabber(1, 0, self.axes, DIR_X1 | DIR_Y0, GrabberRound)
        self.addGrabber(0, 0.5, self.axes, DIR_X0, GrabberRectangle)
        self.axes.figure.canvas.draw()

        self.snaps = []
        # self.snaps.extend(self.parent.snaps)
        self.snap_index_offset = 0  # len(self.snaps)
        #self.snaps = [getSnaps(self.axes, DIR_X0, no_height=True), getSnaps(self.axes, DIR_X1, no_height=True), getSnaps(self.axes, DIR_Y0, no_height=True), getSnaps(self.axes, DIR_Y1, no_height=True)]
        self.snaps = getSnaps(self.axes, DIR_X0 | DIR_X1 | DIR_Y0 | DIR_Y1, no_height=True)

    def save_offset(self):
        # get current position of the text
        pos = self.axes.get_position()
        self.old_pos = pos
        self.ox, self.oy = self.axes.figure.transFigure.transform((pos.x0, pos.y0))
        self.width = pos.width
        self.height = pos.height
        self.w, self.h = self.axes.figure.transFigure.transform((pos.width, pos.height))

    def applyOffset(self, dx, dy):
        x, y = self.ox + dx, self.oy + dy
        x, y = self.axes.figure.transFigure.inverted().transform((x, y))

        pos = self.axes.get_position()

        pos.x0 = x
        pos.y0 = y
        pos.x1 = x + self.width
        pos.y1 = y + self.height

        # set the new position for the text
        self.axes.set_position(pos)

    def update_offset(self, dx, dy, event):
        self.applyOffset(dx, dy)

        if not ("shift" in event.key.split("+") if event.key is not None else False):
            offx, offy = checkSnaps(self.snaps)
            self.applyOffset(dx - offx, dy - offy)

        checkSnapsActive(self.snaps)
        self.updateGrabbers()

    def redoPos(self, pos):
        self.ref_artist.set_position(pos)
        if self.ref_artist.figure.figure_dragger.selected_element == self.ref_artist:
            self.ref_artist.figure.figure_dragger.select_element(None)
        self.on_deselect(None)

    def finalize_offset(self):
        pos = self.ref_artist.get_position()
        self.ref_artist.figure.figure_dragger.addEdit([lambda pos=self.old_pos: self.redoPos(pos), lambda pos=pos: self.redoPos(pos)])
        key = "fig.axes[%d].set_position" % self.ref_artist.number
        self.ref_artist.figure.figure_dragger.addChange(key, key+"([%f, %f, %f, %f])" % (pos.x0, pos.y0, pos.width, pos.height))
        for snap in self.snaps:
            snap.hide()
        self.axes.figure.canvas.draw()

    def moveAxes(self, x, y):
        pos = self.axes.get_position()
        self.axes.set_position([pos.x0 + x, pos.y0 + y, pos.width, pos.height])
        self.updateGrabbers()
        self.axes.figure.canvas.draw()

    def keyPressEvent(self, event):
        if not self.selected:
            return
        # move last axis in z order
        if event.key == 'pagedown':
            self.axes.set_zorder(self.axes.get_zorder() - 1)
            self.axes.figure.canvas.draw()
        if event.key == 'pageup':
            self.axes.set_zorder(self.axes.get_zorder() + 1)
            self.axes.figure.canvas.draw()
        if event.key == 'left':
            self.moveAxes(-0.01, 0)
        if event.key == 'right':
            self.moveAxes(+0.01, 0)
        if event.key == 'down':
            self.moveAxes(0, -0.01)
        if event.key == 'up':
            self.moveAxes(0, +0.01)
        if event.key == "escape":
            self.deselectArtist()


class DraggableText(DraggableBase):
    def __init__(self, text, use_blit=False):
        DraggableBase.__init__(self, text, use_blit=use_blit)
        self.text = text

    def save_offset(self):
        # get current position of the text
        self.old_pos = self.text.get_position()
        self.ox, self.oy = self.text.get_transform().transform(self.text.get_position())
        # add snaps
        self.snaps = []
        fig = self.text.figure
        for ax in fig.axes + [fig]:
            for txt in ax.texts:
                # for other texts
                if txt == self.text:
                    continue
                # snap to the x and the y coordinate
                x, y = txt.get_transform().transform(txt.get_position())
                self.snaps.append(snapSamePos(self.text, txt, 0))
                self.snaps.append(snapSamePos(self.text, txt, 1))


    def applyOffset(self, dx, dy):
        x, y = self.ox + dx, self.oy + dy
        self.text.set_position(self.text.get_transform().inverted().transform((x, y)))

    def update_offset(self, dx, dy, event):
        self.applyOffset(dx, dy)

        if not ("shift" in event.key.split("+") if event.key is not None else False):
            offx, offy = checkSnaps(self.snaps)
            self.applyOffset(dx - offx, dy - offy)

        checkSnapsActive(self.snaps)

    def redoPos(self, pos):
        self.ref_artist.set_position(pos)
        self.deselectArtist()

    def finalize_offset(self):
        pos = self.ref_artist.get_position()
        self.ref_artist.figure.figure_dragger.addEdit(
            [lambda pos=self.old_pos: self.redoPos(pos), lambda pos=pos: self.redoPos(pos)])
        if self.ref_artist.axes:
            index0 = self.ref_artist.axes.number
            index1 = self.ref_artist.axes.texts.index(self.ref_artist)
            key = "fig.axes[%d].texts[%d].set_position" % (index0, index1)
        else:
            index1 = self.ref_artist.figure.texts.index(self.ref_artist)
            key = "fig.texts[%d].set_position" % (index1)
        self.ref_artist.figure.figure_dragger.addChange(key, key + "([%f, %f])  # Text: \"%s\"" % (pos[0], pos[1], self.ref_artist.get_text()))
        # remove all snaps when the dragger is released
        for snap in self.snaps:
            snap.remove()


class DraggableOffsetBox(DraggableBase):
    def __init__(self, ref_artist, offsetbox, use_blit=False):
        DraggableBase.__init__(self, ref_artist, use_blit=use_blit)
        self.offsetbox = offsetbox

    def save_offset(self):
        offsetbox = self.offsetbox
        renderer = offsetbox.figure._cachedRenderer
        w, h, xd, yd = offsetbox.get_extent(renderer)
        offset = offsetbox.get_offset(w, h, xd, yd, renderer)
        self.offsetbox_x, self.offsetbox_y = offset
        self.offsetbox.set_offset(offset)
        self.old_pos = self.get_loc_in_canvas()

    def update_offset(self, dx, dy, event):
        loc_in_canvas = self.offsetbox_x + dx, self.offsetbox_y + dy
        self.offsetbox.set_offset(loc_in_canvas)

    def get_loc_in_canvas(self):

        offsetbox = self.offsetbox
        renderer = offsetbox.figure._cachedRenderer
        w, h, xd, yd = offsetbox.get_extent(renderer)
        ox, oy = offsetbox._offset
        loc_in_canvas = (ox - xd, oy - yd)

        return loc_in_canvas


class DraggableLegend(DraggableOffsetBox):
    def __init__(self, legend, use_blit=False, update="loc"):
        """
        update : If "loc", update *loc* parameter of
                 legend upon finalizing. If "bbox", update
                 *bbox_to_anchor* parameter.
        """
        self.legend = legend

        if update in ["loc", "bbox"]:
            self._update = update
        else:
            raise ValueError("update parameter '%s' is not supported." %
                             update)

        DraggableOffsetBox.__init__(self, legend, legend._legend_box,
                                    use_blit=use_blit)

    def artist_picker(self, legend, evt):
        return self.legend.contains(evt)

    def redoPos(self, loc_in_canvas):
        self.offsetbox.set_offset(loc_in_canvas)

    def finalize_offset(self):
        loc_in_canvas = self.get_loc_in_canvas()
        self.ref_artist.figure.figure_dragger.addEdit(
            [lambda pos=self.old_pos: self.redoPos(pos), lambda pos=loc_in_canvas: self.redoPos(pos)])

        if self._update == "loc":
            self._update_loc(loc_in_canvas)
        elif self._update == "bbox":
            self._update_bbox_to_anchor(loc_in_canvas)
        else:
            raise RuntimeError("update parameter '%s' is not supported." %
                               self.update)

        loc = self.ref_artist._get_loc()
        index1 = self.ref_artist.axes.number
        key = "fig.axes[%d].get_legend()._set_loc" % (index1)
        self.ref_artist.figure.figure_dragger.addChange(key, key + "(%s)" % (loc,))
        #save_text += "fig.axes[%d].get_legend()._set_loc(%s)\n" % (index, loc)

    def _update_loc(self, loc_in_canvas):
        bbox = self.legend.get_bbox_to_anchor()

        # if bbox has zero width or height, the transformation is
        # ill-defined. Fall back to the defaul bbox_to_anchor.
        if bbox.width == 0 or bbox.height == 0:
            self.legend.set_bbox_to_anchor(None)
            bbox = self.legend.get_bbox_to_anchor()

        _bbox_transform = BboxTransformFrom(bbox)
        self.legend._loc = tuple(
            _bbox_transform.transform_point(loc_in_canvas)
        )
        print(tuple(
            _bbox_transform.transform_point(loc_in_canvas)
        ))

    def _update_bbox_to_anchor(self, loc_in_canvas):

        tr = self.legend.axes.transAxes
        loc_in_bbox = tr.transform_point(loc_in_canvas)

        self.legend.set_bbox_to_anchor(loc_in_bbox)


def StartPylustration(xsnaps=None, ysnaps=None, unit="cm"):
    import matplotlib as mpl
    mpl.rcParams['keymap.back'].remove('left')
    mpl.rcParams['keymap.forward'].remove('right')

    # add a dragger for each figure
    for i in plt.get_fignums():
        print("add difgure dragger", plt.figure(i))
        FigureDragger(plt.figure(i), xsnaps, ysnaps, unit)
