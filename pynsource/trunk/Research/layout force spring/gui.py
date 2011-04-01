import wx
import wx.lib.ogl as ogl
import time
import thread

from graph import *
from layout_spring import GraphLayoutSpring
from overlap_removal import OverlapRemoval
import random

def setpos(shape, x, y):
    width, height = shape.GetBoundingBoxMax()
    shape.SetX( x + width/2 )
    shape.SetY( y + height/2 )
def getpos(shape):
    width, height = shape.GetBoundingBoxMax()
    x = shape.GetX()
    y = shape.GetY()
    return (x - width/2, y - height/2)


class MyEvtHandler(ogl.ShapeEvtHandler):
    def __init__(self, log, oglcanvas):
        ogl.ShapeEvtHandler.__init__(self)
        self.log = log
        self.oglcanvas = oglcanvas

    def UpdateStatusBar(self, shape):
        x, y = shape.GetX(), shape.GetY()
        x, y = getpos(shape)
        width, height = shape.GetBoundingBoxMax()
        frame = self.oglcanvas.GetTopLevelParent()
        frame.SetStatusText("Pos: (%d,%d)  Size: (%d, %d)  -  GraphNode is %s" % (x, y, width, height, shape.node))

    def OnLeftClick(self, x, y, keys = 0, attachment = 0):
        #print "OnLeftClick"
        shape = self.GetShape()
        
        # size handles
        shape.GetCanvas().graphrendererogl.DeselectAllShapes()
        shape.Select(True, None)
        shape.GetCanvas().graphrendererogl.stateofthenation()
        
        self.UpdateStatusBar(shape)
            
    def OnDrawOutline(self, dc, x, y, w, h):
        ogl.ShapeEvtHandler.OnDrawOutline(self, dc, x, y, w, h)
        shape = self.GetShape()
        x,y = (x - w/2, y - h/2) # correct to be top corner not centre
        frame.SetStatusText("Pos: (%d,%d)  Size: (%d, %d)  -  GraphNode is %s" % (x, y, w, h, shape.node))
        
    def OnDragLeft(self, draw, x, y, keys = 0, attachment = 0):
        ogl.ShapeEvtHandler.OnDragLeft(self, draw, x, y, keys = 0, attachment = 0)
        # x, y are the merely the mouse position thus useless for getting to shape x,y - intercept OnDrawOutline instead 
        
    def OnEndDragLeft(self, x, y, keys = 0, attachment = 0):
        shape = self.GetShape()

        # take care of selection points
        ogl.ShapeEvtHandler.OnEndDragLeft(self, x, y, keys, attachment)
        if not shape.Selected():
            self.OnLeftClick(x, y, keys, attachment)
        
        oldpos = getpos(shape) # (int(shape.GetX()), int(shape.GetY()))
        ogl.ShapeEvtHandler.OnEndDragLeft(self, x, y, keys, attachment)  # super
        newpos = getpos(shape) # (int(shape.GetX()), int(shape.GetY()))

        print shape.node.id, "moved from", oldpos, "to", newpos
        
        # Adjust the GraphNode to match the shape x,y
        shape.node.left, shape.node.top = newpos

        self.UpdateStatusBar(shape)

        wx.SafeYield()
        time.sleep(0.2)
        
        shape.GetCanvas().graphrendererogl.stage2()

    def OnSizingEndDragLeft(self, pt, x, y, keys, attch):
        shape = self.GetShape()

        # super        
        ogl.ShapeEvtHandler.OnSizingEndDragLeft(self, pt, x, y, keys, attch)
        
        width, height = shape.GetBoundingBoxMin()
        print shape.node, "resized to", width, height
        #print shape.node.id, shape.node.left, shape.node.top, "resized to", width, height
        # Adjust the GraphNode to match the shape x,y
        shape.node.width, shape.node.height = width, height
        shape.node.left, shape.node.top = getpos(shape)
        
        self.UpdateStatusBar(self.GetShape())

        wx.SafeYield()
        time.sleep(0.2)
        
        shape.GetCanvas().graphrendererogl.stage2()

        
class GraphShapeCanvas(ogl.ShapeCanvas):
    scrollStepX = 10
    scrollStepY = 10
    classnametoshape = {}

    def __init__(self, parent):
        ogl.ShapeCanvas.__init__(self, parent)

    def OnLeftClick(self, x, y, keys):  # Override of ShapeCanvas method
        # keys is a bit list of the following: KEY_SHIFT  KEY_CTRL
        self.graphrendererogl.DeselectAllShapes()

from coordinate_mapper import CoordinateMapper

UNIT_TESTING_MODE = True

class GraphRendererOgl:
    def __init__(self, graph, oglcanvas):
        self.graph = graph
        self.oglcanvas = oglcanvas
        self.oglcanvas.graphrendererogl = self
        self.coordmapper = CoordinateMapper(self.graph, self.oglcanvas.GetSize())

        self.oglcanvas.Bind(wx.EVT_MOUSEWHEEL, self.OnWheelZoom)
        self.oglcanvas.Bind(wx.EVT_RIGHT_DOWN, self.OnRightButtonMenu)
        self.oglcanvas.Bind(wx.EVT_KEY_DOWN, self.onKeyPress)
        self.oglcanvas.Bind(wx.EVT_CHAR, self.onKeyChar)
        self.oglcanvas.Bind(wx.EVT_SIZE, self.OnResizeFrame)
        
        self.popupmenu = None
        self.need_abort = False
        self.new_edge_from = None
        self.working = False
        self.mementos = None

        if UNIT_TESTING_MODE:
            self.overlap_remover = OverlapRemoval(self.graph, margin=5, gui=self)
        else:
            self.overlap_remover = OverlapRemoval(self.graph, margin=50, gui=self)

    def AllToLayoutCoords(self):
            self.coordmapper.AllToLayoutCoords()

    def AllToWorldCoords(self):
            self.coordmapper.AllToWorldCoords()

    def DeselectAllShapes(self):
        selected = [s for s in self.oglcanvas.GetDiagram().GetShapeList() if s.Selected()]
        if selected:
            s = selected[0]
            canvas = s.GetCanvas()
            dc = wx.ClientDC(canvas)
            canvas.PrepareDC(dc)
            s.Select(False, dc)
            canvas.Refresh(False)   # Need this or else Control points ('handles') leave blank holes      

    def InsertNewNode(self):
        id = 'D' + str(random.randint(1,99))
        dialog = wx.TextEntryDialog ( None, 'Enter an id string:', 'Create a new node', id )
        if dialog.ShowModal() == wx.ID_OK:
            id = dialog.GetValue()
            if self.graph.FindNodeById(id):
                id += str(random.randint(1,9999))
            node = GraphNode(id, random.randint(0, 100),random.randint(0,100),random.randint(60, 160),random.randint(60,160))
            node = self.graph.AddNode(node)
            self.createNodeShape(node)
            node.shape.Show(True)
            self.stateofthenation()
        dialog.Destroy()

    def DeleteSelectedNode(self):
        selected = [s for s in self.oglcanvas.GetDiagram().GetShapeList() if s.Selected()]
        if selected:
            shape = selected[0]
            print 'delete', shape.node.id

            # model
            self.graph.DeleteNodeById(shape.node.id)

            # view
            self.DeselectAllShapes()
            for line in shape.GetLines()[:]:
                line.Delete()
            shape.Delete()

    def OnResizeFrame (self, event):   # ANDY  interesting - GetVirtualSize grows when resize frame
        frame = self.oglcanvas.GetTopLevelParent()
        print "frame resize", frame.GetClientSize()
        self.coordmapper.Recalibrate(frame.GetClientSize()) # may need to call self.CalcVirtSize() if scrolled window
   
    def onKeyPress(self, event):
        keycode = event.GetKeyCode()  # http://www.wxpython.org/docs/api/wx.KeyEvent-class.html
        #if event.ShiftDown():
        #if event.ControlDown():
        #print keycode
        #print chr(keycode)
        #print ord('L')

        if keycode == wx.WXK_DOWN:
            if self.working: return
            self.working = True
            optimise = not event.ShiftDown()
            self.ReLayout(keep_current_positions=True, gui=self, optimise=optimise)
            self.working = False

        elif keycode == wx.WXK_UP:
            if self.working: return
            self.working = True
            print "keep_current_positions=False"
            optimise = not event.ShiftDown()
            self.ReLayout(keep_current_positions=False, gui=self, optimise=optimise)
            self.working = False
            
        elif keycode == wx.WXK_RIGHT:
            if self.working: return
            self.working = True
            if self.coordmapper.scale > 0.8:
                self.ChangeScale(-0.2, remap_world_to_layout=event.ShiftDown())
                print "expansion ", self.coordmapper.scale
            else:
                print "Max expansion prevented.", self.coordmapper.scale
            self.working = False
            
        elif keycode == wx.WXK_LEFT:
            if self.working: return
            self.working = True
            if self.coordmapper.scale < 3:
                self.ChangeScale(0.2, remap_world_to_layout=event.ShiftDown())
                print "contraction ", self.coordmapper.scale
            else:
                print "Min expansion thwarted.", self.coordmapper.scale
            self.working = False
            
        elif keycode == wx.WXK_DELETE:
            self.DeleteSelectedNode()

        elif keycode == wx.WXK_INSERT:
            self.InsertNewNode()

        event.Skip()

    def onKeyChar(self, event):
        if event.GetKeyCode() >= 256:
            event.Skip()
            return
        
        keycode = chr(event.GetKeyCode())

        if keycode == 'q':
            self.NewEdgeMarkFrom()

        elif keycode == 'w':
            self.NewEdgeMarkTo()
            
        if keycode in ['1','2','3','4','5','6','7','8','9','0']:
            if not self.mementos:
                return
            
            if self.working: return
            self.working = True
            
            todisplay = ord(keycode) - ord('1')
            if todisplay < len(self.mementos):
                self.DisplayMemento(self.mementos[todisplay][5], self.mementos[todisplay][3])
            else:
                print "No such memento", todisplay

            self.DumpMementos(todisplay)
            self.DumpStatus()

            self.working = False

        elif keycode in ['x', 'X', 'z', 'Z']:
            """
            x = layout a few times to untangle then scale up till line-node crossings low
            z = layout a few times to untangle then scale up till natural node overlaps low (don't apply overlap removal till end)
            """
            if self.working: return
            self.working = True
            
            self.AllToLayoutCoords()  # doesn't matter what scale layout starts with
            
            # Scale up just for watching...
            self.coordmapper.Recalibrate(scale=1.4)
            layouter = GraphLayoutSpring(self.graph, gui=self)    # should keep this around
            
            scramble = keycode in ['X','Z']
            layouter.layout(keep_current_positions=not scramble)

            if keycode in ['Z','z']:
                strategy = ":reduce pre overlap removal NN overlaps"
            else:
                strategy = ":reduce post overlap removal LN and LL crossings"
                #strategy = ":reduce post overlap removal LN crossings"
            self.ScaleUpMadly(strategy)
            
            self.working = False
            

        elif keycode in ['c', 'C']:
            """
            Relayout till nothing seems to move anymore in real world coordingate
            Stay at same scale
            
            DEFUNCT - integrated this algorithm into the lower level spring layout,
            operating on layout coords.  Spring Layout itself drops out early if nothing changing.
            """
            if self.working: return
            self.working = True
            
            layouter = GraphLayoutSpring(self.graph, gui=self)

            # layout a few times
            self.AllToLayoutCoords()
            memento1 = self.graph.GetMementoOfPositions()
            
            if keycode == 'C':
                layouter.layout(keep_current_positions=False)
            else:
                layouter.layout(keep_current_positions=True)

            for i in range(1, 15):            
                self.AllToWorldCoords()
                memento2 = self.graph.GetMementoOfPositions()
                
                if Graph.MementosEqual(memento1, memento2):
                    print "Layout %d World Position Mementos Equal - break" % i
                    break
                else:
                    print "Layout %d World Positions in flux - keep trying" % i
                    layouter.layout(keep_current_positions=True)

                #layouter.layout(keep_current_positions=True)
                memento1 = memento2
            
            self.AllToWorldCoords()
            self.stage2() # does overlap removal and stateofthenation

            self.working = False

        elif keycode in ['b', 'B']:
            if self.working: return
            self.working = True
            
            """
            Blackboard
            Rerun layout several times, remembering each as a memento.  Then pick the best.
            
            First layout memento (pre ScaleUpMadly() should be at ?? scale OR PERHAPS
            WE DONT NEED TO REMEMBER THIS ONE AS IT GETS COVERED IN THE ScaleUpMadly() ANYWAY.
            
            Coordinate scaling runs 3.2 to max within ScaleUpMadly()
            Finish at the scale chosen by this routine
            """
            self.AllToLayoutCoords()
            layouter = GraphLayoutSpring(self.graph, gui=None)
            self.mementos = []
            #save_scale = self.coordmapper.scale

            # Generate a few totally fresh layout variations
            for i in range(3):
                layouter.layout(keep_current_positions=False)
                
                #self.coordmapper.Recalibrate(scale=save_scale) # need this if scale changed
                #self.AllToWorldCoords()  # need this if gui animation off
                #self.overlap_remover.RemoveOverlaps()  # you DO want to take into account a post overlap removal situation
                #num_line_line_crossings = len(self.graph.CountLineOverLineIntersections())
                #num_line_node_crossings = self.graph.CountLineOverNodeCrossings()['ALL']/2    # ignore? 
                
                scale, num_line_line_crossings, num_node_node_overlaps, num_line_node_crossings = \
                    self.ScaleUpMadly(strategy=":reduce post overlap removal LN crossings")
                memento = self.graph.GetMementoOfPositions()
                self.mementos.append((num_line_line_crossings,
                                      num_node_node_overlaps,
                                      num_line_node_crossings,
                                      scale,
                                      88,
                                      memento))
                    
                #self.stateofthenation()
                #wx.SafeYield()
            
            self.DumpMementos()
            print "sort"
            self.mementos.sort()  # should sort by 1st item in tuple, followed by next item in tuple etc. - perfect!
            self.DumpMementos()
            
            self.DisplayMemento(self.mementos[0][5], self.mementos[0][3])

            self.working = False
            
        elif keycode == 'l':
            print self.graph.CountLineOverNodeCrossings()

        elif keycode in ['?',]:
            self.DumpStatus()
            
        event.Skip()

    def DumpStatus(self):
        print "-"*50
        print "# line-line intersections", len(self.graph.CountLineOverLineIntersections())
        print "# node-node overlaps (post overlap removal always ~ 0)", self.overlap_remover.CountOverlaps()
        print "# line-node crossings", self.graph.CountLineOverNodeCrossings()['ALL']/2
        print "scale", self.coordmapper.scale
        print "bounds ?"
        
    def DisplayMemento(self, memento, scale):
        self.graph.RestoreWorldPositions(memento)
        self.stateofthenation()

        # Unecessary, but just in case you choose to <- or -> "scale from layout" next
        self.coordmapper.Recalibrate(scale=scale)
        self.AllToLayoutCoords() 
            
        
    def DumpMementos(self, current_i=-1):
        print '-'*80
        for i, memento in enumerate(self.mementos):
            msg = ""
            if i == current_i:
                msg = " <---"
            print "Memento %d has info LL %d NN %d LN %d scale %.1f bounds %d %s" % (i+1, memento[0], memento[1], memento[2], memento[3], memento[4], msg)

    def ScaleUpMadly(self, strategy):
        """
        Leaves the scale at max level it got to - doesn't restore scale

        strategy = ":reduce pre overlap removal NN overlaps"
        strategy = ":reduce post overlap removal LN crossings"
        
        Operates repeatedly on the layout coords, so ignores anything you
        have done since, like world coord overlap removal.

        Running overlap removal at different scales can remove or introduce
        LL and LN crossings (but by definition, no NN overlaps ;-)
        
        After AllToWorldCoords() we are getting a picture of the pure layout result
        
        Calling self.coordmapper.Recalibrate(scale) before AllToWorldCoords() simply
        expands or contracts the appearance of the world view nodes
        
        After AllToWorldCoords(), looking at pure layout result there will typically be
         -- LL == 0, unless the spring layout couldn't untangle itself, that is.
         *- NN many, scaling up helps reduce (running overlap remover removes totally)
         -- LN many, scaling up helps reduce (running overlap remover may make it better or worse)
        
        After RemoveOverlaps()
         *- LL == 0
         -- NN == 0, unless algorithm failed
         *- LN some
         
         Note: * indicates the things we are looping and testing
        """
        NODE_NODE = 3
        MAX_SCALE = 1.4
        SCALE_STEP = 0.2
        SCALE_START = 3.2
        
        self.coordmapper.Recalibrate(scale=SCALE_START)
        for i in range(15):
            self.coordmapper.Recalibrate(scale=self.coordmapper.scale - SCALE_STEP)
            self.AllToWorldCoords()

            """Pre Overlap Removal"""
            
            # see how many INITIAL, PRE OVERLAP REMOVAL line-line crossings there are.
            num_line_line_crossings = len(self.graph.CountLineOverLineIntersections())
            if num_line_line_crossings > 0:
                print "Mad: Aborting - no point since found %d tangled, post spring layout LL crossings!" % num_line_line_crossings
                break

            # see how many INITIAL, PRE OVERLAP REMOVAL node-node overlaps the expansion fixes
            num_node_node_overlaps = self.overlap_remover.CountOverlaps()

            """Remove Overlaps (NN)"""
            self.overlap_remover.RemoveOverlaps(watch_removals=False)

            """Post Overlap Removal"""

            # How many LN reduced (or perhaps increased) after expansion & post removing NN overlaps
            num_line_node_crossings = self.graph.CountLineOverNodeCrossings()['ALL']/2
            
            # How many LL reduced (or perhaps increased) after expansion & post removing NN overlaps
            num_line_line_crossings = len(self.graph.CountLineOverLineIntersections())

            print "Mad: At scale %.1f LL %d NN %d LN %d" % (self.coordmapper.scale, num_line_line_crossings, num_node_node_overlaps, num_line_node_crossings)
        
            if strategy == ":reduce pre overlap removal NN overlaps":
                if num_node_node_overlaps <= NODE_NODE:
                    print "Mad: Aborting expansion since num NN overlaps <= %d" % NODE_NODE
                    break
            elif strategy == ":reduce post overlap removal LN crossings":
                if num_line_node_crossings == 0:
                    print "Mad: Finished expansion since LN crossings == 0 :-)"
                    break
            elif strategy == ":reduce post overlap removal LN and LL crossings":
                if num_line_node_crossings == 0 and num_line_node_crossings == 0:
                    print "Mad: Finished expansion since LN and LL crossings == 0 :-)"
                    break
            else:
                assert False, "Mad: unknown strategy"
    
            # Never accept LN crossings introduced as a result of expansion
            #if num_line_node_crossings > 0:
            #    print "Mad: Warning - introduced LN crossings as a result of expansion, expanding more..."
            #    continue  # risky since we avoid MAX_SCALE check
            
            if self.coordmapper.scale < MAX_SCALE:
                print "Mad: Aborting expansion - gone too far."
                break
    
        print "Mad: End - scale ended up as ", self.coordmapper.scale

        #self.stage2() # does overlap removal and stateofthenation
        
        return self.coordmapper.scale, num_line_line_crossings, num_node_node_overlaps, num_line_node_crossings


    def NewEdgeMarkFrom(self):
        selected = [s for s in self.oglcanvas.GetDiagram().GetShapeList() if s.Selected()]
        if not selected:
            print "Please select a node"
            return
        
        self.new_edge_from = selected[0].node
        print "From", self.new_edge_from.id

    def NewEdgeMarkTo(self):
        selected = [s for s in self.oglcanvas.GetDiagram().GetShapeList() if s.Selected()]
        if not selected:
            print "Please select a node"
            return
        
        tonode = selected[0].node
        print "To", tonode.id
        
        if self.new_edge_from == None:
            print "Please set from node first"
            return
        
        if self.new_edge_from.id == tonode.id:
            print "Can't link to self"
            return
        
        if not self.graph.FindNodeById(self.new_edge_from.id):
            print "From node %s doesn't seem to be in graph anymore!" % self.new_edge_from.id
            return
        
        edge = self.graph.AddEdge(self.new_edge_from, tonode, weight=None)
        self.createEdgeShape(edge)
        self.stateofthenation()

    def OnWheelZoom(self, event):
        if self.working: return
        self.working = True

        if event.GetWheelRotation() < 0:
            self.stage2()
            print self.overlap_remover.GetStats()
        else:
            self.stateofthenation()

        self.working = False

    def draw(self, translatecoords=True):
        self.stage1(translatecoords=translatecoords)
        #thread.start_new_thread(self.DoSomeLongTask, ())

    def stage1(self, translatecoords=True):
        import time
        
        if translatecoords:
            self.AllToWorldCoords()

        for node in self.graph.nodes:
            self.createNodeShape(node)
        for edge in self.graph.edges:
            self.createEdgeShape(edge)

        self.Redraw()
        #time.sleep(1)

    def stage2(self, force_stateofthenation=False, watch_removals=True):
        self.overlap_remover.RemoveOverlaps(watch_removals=watch_removals)
        if self.overlap_remover.GetStats()['total_overlaps_found'] > 0 or force_stateofthenation:
            self.stateofthenation()
        
    def stateofthenation(self):
        for node in self.graph.nodes:
            self.AdjustShapePosition(node)
        self.Redraw()
        wx.SafeYield()
        #time.sleep(0.2)
        
    def stateofthespring(self):
        self.coordmapper.Recalibrate()
        self.AllToWorldCoords()
        self.stateofthenation() # DON'T do overlap removal or it will get mad!

    def ChangeScale(self, delta, remap_world_to_layout=False):
        if remap_world_to_layout:
            self.AllToLayoutCoords()    # Experimental - only needed when you've done world coord changes 
        self.coordmapper.Recalibrate(scale=self.coordmapper.scale+delta)
        self.AllToWorldCoords()
        numoverlaps = self.overlap_remover.CountOverlaps()
        #print "Num Node Overlaps at scale", self.coordmapper.scale, numoverlaps
        
        
        #saveit = self.overlap_remover.gui
        #self.overlap_remover.gui = None
        #self.stage2(force_stateofthenation=True) # does overlap removal and stateofthenation
        #self.overlap_remover.gui = saveit

        self.stage2(force_stateofthenation=True, watch_removals=False) # does overlap removal and stateofthenation
        
    def ReLayout(self, keep_current_positions=False, gui=None, optimise=True):
        # layout again
        #print "spring layout again!"
        self.AllToLayoutCoords()

        layouter = GraphLayoutSpring(self.graph, gui)    # should keep this around
        layouter.layout(keep_current_positions, optimise=optimise)
        
        self.AllToWorldCoords()
        self.stage2() # does overlap removal and stateofthenation
        #self.stateofthenation()
        
    def OnRightButtonMenu(self, event):   # Menu
        x, y = event.GetPosition()
        frame = self.oglcanvas.GetTopLevelParent()
        
        if self.popupmenu:
            self.popupmenu.Destroy()    # wx.Menu objects need to be explicitly destroyed (e.g. menu.Destroy()) in this situation. Otherwise, they will rack up the USER Objects count on Windows; eventually crashing a program when USER Objects is maxed out. -- U. Artie Eoff  http://wiki.wxpython.org/index.cgi/PopupMenuOnRightClick
        self.popupmenu = wx.Menu()     # Create a menu
        
        item = self.popupmenu.Append(2015, "Load Graph from text...")
        frame.Bind(wx.EVT_MENU, self.OnLoadGraphFromText, item)
        
        item = self.popupmenu.Append(2017, "Dump Graph to console")
        frame.Bind(wx.EVT_MENU, self.OnSaveGraphToConsole, item)

        self.popupmenu.AppendSeparator()

        item = self.popupmenu.Append(2011, "Load Graph...")
        frame.Bind(wx.EVT_MENU, self.OnLoadGraph, item)
        
        item = self.popupmenu.Append(2012, "Save Graph...")
        frame.Bind(wx.EVT_MENU, self.OnSaveGraph, item)

        self.popupmenu.AppendSeparator()

        item = self.popupmenu.Append(2016, "Load Test Graph 1")
        frame.Bind(wx.EVT_MENU, self.OnLoadTestGraph1, item)

        item = self.popupmenu.Append(2018, "Load Test Graph 2")
        frame.Bind(wx.EVT_MENU, self.OnLoadTestGraph2, item)

        item = self.popupmenu.Append(2019, "Load Test Graph 3")
        frame.Bind(wx.EVT_MENU, self.OnLoadTestGraph3, item)

        item = self.popupmenu.Append(2020, "Load Test Graph 4")
        frame.Bind(wx.EVT_MENU, self.OnLoadTestGraph4, item)

        self.popupmenu.AppendSeparator()

        item = self.popupmenu.Append(2014, "Clear")
        frame.Bind(wx.EVT_MENU, self.OnClear, item)  # must pass item

        item = self.popupmenu.Append(2013, "Cancel")
        #frame.Bind(wx.EVT_MENU, self.OnPopupItemSelected, item)
        
        frame.PopupMenu(self.popupmenu, wx.Point(x,y))

            
    def OnSaveGraphToConsole(self, event):
        print self.graph.GraphToString()

    def OnSaveGraph(self, event):
        frame = self.oglcanvas.GetTopLevelParent()
        dlg = wx.FileDialog(parent=frame, message="choose", defaultDir='.',
            defaultFile="", wildcard="*.txt", style=wx.FD_SAVE, pos=wx.DefaultPosition)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            
            fp = open(filename, "w")
            fp.write(self.graph.GraphToString())
            fp.close()
            
        dlg.Destroy()
        
    def OnLoadTestGraph1(self, event):
        filedata = """
{'type':'node', 'id':'D25', 'x':7, 'y':6, 'width':159, 'height':106}
{'type':'node', 'id':'D13', 'x':6, 'y':119, 'width':119, 'height':73}
{'type':'node', 'id':'m1', 'x':171, 'y':9, 'width':139, 'height':92}
        """
        self.LoadGraph(filedata)
        
    def OnLoadTestGraph2(self, event):
        filedata = """
{'type':'node', 'id':'D25', 'x':7, 'y':6, 'width':159, 'height':106}
{'type':'node', 'id':'D13', 'x':6, 'y':119, 'width':119, 'height':73}
{'type':'node', 'id':'m1', 'x':146, 'y':179, 'width':139, 'height':92}
{'type':'node', 'id':'D97', 'x':213, 'y':6, 'width':85, 'height':159}
        """
        self.LoadGraph(filedata)
        
    def OnLoadTestGraph3(self, event):
        filedata = """
{'type':'node', 'id':'D25', 'x':7, 'y':6, 'width':159, 'height':106}
{'type':'node', 'id':'D13', 'x':6, 'y':119, 'width':119, 'height':73}
{'type':'node', 'id':'m1', 'x':246, 'y':179, 'width':139, 'height':92}
{'type':'node', 'id':'D97', 'x':213, 'y':6, 'width':85, 'height':159}
{'type':'node', 'id':'D98', 'x':340, 'y':7, 'width':101, 'height':107}
        """
        self.LoadGraph(filedata)

    def OnLoadTestGraph4(self, event):
        filedata = """
{'type':'node', 'id':'D25', 'x':7, 'y':6, 'width':159, 'height':106}
{'type':'node', 'id':'D13', 'x':6, 'y':119, 'width':119, 'height':73}
{'type':'node', 'id':'m1', 'x':6, 'y':214, 'width':139, 'height':92}
{'type':'node', 'id':'D97', 'x':213, 'y':6, 'width':85, 'height':159}
{'type':'node', 'id':'D98', 'x':305, 'y':57, 'width':101, 'height':107}
{'type':'node', 'id':'D50', 'x':149, 'y':184, 'width':242, 'height':112}
{'type':'node', 'id':'D51', 'x':189, 'y':302, 'width':162, 'height':66}
        """
        self.LoadGraph(filedata)

    def OnLoadGraphFromText(self, event):
        eg = "{'type':'node', 'id':'A', 'x':142, 'y':129, 'width':250, 'height':250}"
        dialog = wx.TextEntryDialog ( None, 'Enter an node/edge persistence strings:', 'Create a new node', eg,  style=wx.OK|wx.CANCEL|wx.TE_MULTILINE )
        if dialog.ShowModal() == wx.ID_OK:
            txt = dialog.GetValue()
            self.LoadGraph(txt)
            
    def OnLoadGraph(self, event):
        frame = self.oglcanvas.GetTopLevelParent()
        dlg = wx.FileDialog(parent=frame, message="choose", defaultDir='.',
            defaultFile="", wildcard="*.txt", style=wx.OPEN, pos=wx.DefaultPosition)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()

            fp = open(filename, "r")
            s = fp.read()
            fp.close()

            self.LoadGraph(s)
        dlg.Destroy()

    def LoadGraph(self, filedata=""):
        self.Clear()
        
        self.graph.LoadGraphFromStrings(filedata)
                
        # build view from model
        self.draw(translatecoords=False)
        
        # refresh view
        self.oglcanvas.GetDiagram().ShowAll(1) # need this, yes
        self.stateofthenation()

    def OnClear(self, event):
        self.Clear()
        
    def Clear(self):
        # Clear view        
        self.oglcanvas.GetDiagram().DeleteAllShapes()
        dc = wx.ClientDC(self.oglcanvas)
        self.oglcanvas.GetDiagram().Clear(dc)   # only ends up calling dc.Clear() - I wonder if this clears the screen?
        
        # clear model
        self.graph.Clear()
        
    def DoSomeLongTask(self):
        
        for i in range(1,50):
            if self.need_abort:
                print "aborted."
                return
            wx.CallAfter(self.stage2)
            #print '*',
            #wx.CallAfter(self.DoStuff)
            time.sleep(2)   # lets events through to the main wx thread and paints/messages get through ok
        print "Done."
        
        """
        print "Task started"
        if self.need_abort:
            print "aborted."
            return
        wx.CallAfter(self.stage1)
        #time.sleep(0.5)   # lets events through to the main wx thread and paints/messages get through ok
        #wx.CallAfter(self.stage2)
        print "Done."
        """
        
        
    def AdjustShapePosition(self, node):
        assert node.shape
        
        # Don't need to use node.shape.Move(dc, x, y, False)
        setpos(node.shape, node.left, node.top)

        # But you DO need to use a dc to adjust the links
        dc = wx.ClientDC(self.oglcanvas)
        self.oglcanvas.PrepareDC(dc)
        node.shape.MoveLinks(dc)

        
    def Redraw(self):
        
        diagram = self.oglcanvas.GetDiagram()
        canvas = self.oglcanvas
        assert canvas == diagram.GetCanvas()

        dc = wx.ClientDC(canvas)
        canvas.PrepareDC(dc)
        
        #for node in self.graph.nodes:    # TODO am still moving nodes in the pynsourcegui version?
        #    shape = node.shape
        #    shape.Move(dc, shape.GetX(), shape.GetY())
        diagram.Clear(dc)
        diagram.Redraw(dc)

     
    def createNodeShape(self, node):
        shape = ogl.RectangleShape( node.width, node.height )
        shape.AddText(node.id)
        setpos(shape, node.left, node.top)
        #shape.SetDraggable(True, True)
        self.oglcanvas.AddShape( shape )
        node.shape = shape
        shape.node = node
        
        # wire in the event handler for the new shape
        evthandler = MyEvtHandler(None, self.oglcanvas)
        evthandler.SetShape(shape)
        evthandler.SetPreviousHandler(shape.GetEventHandler())
        shape.SetEventHandler(evthandler)
       
    def createEdgeShape(self, edge):
        line = ogl.LineShape()
        line.SetCanvas(self.oglcanvas)
        line.SetPen(wx.BLACK_PEN)
        line.SetBrush(wx.BLACK_BRUSH)
        line.MakeLineControlPoints(2)
       
        fromShape = edge['source'].shape
        toShape = edge['target'].shape
        fromShape.AddLine(line, toShape)
        self.oglcanvas.GetDiagram().AddShape(line)
        line.Show(True)        
        

class AppFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__( self,
                          None, -1, "Andy's UML Layout Experimentation Sandbox",
                          size=(800,800),
                          style=wx.DEFAULT_FRAME_STYLE )
        sizer = wx.BoxSizer( wx.VERTICAL )
        # put stuff into sizer

        self.CreateStatusBar()

        canvas = GraphShapeCanvas(self) # ogl.ShapeCanvas( self )
        sizer.Add( canvas, 1, wx.GROW )

        canvas.SetBackgroundColour( "LIGHT BLUE" ) #

        diagram = ogl.Diagram()
        canvas.SetDiagram( diagram )
        diagram.SetCanvas( canvas )

        ## ==========================================
        
        g = Graph()
        
        a = GraphNode('A', 0, 0, 250, 250)
        a1 = GraphNode('A1', 0, 0)
        a2 = GraphNode('A2', 0, 0)
        g.AddEdge(a, a1)
        g.AddEdge(a, a2)

        b = GraphNode('B', 0, 0)
        b1 = GraphNode('B1', 0, 0)
        b2 = GraphNode('B2', 0, 0)
        g.AddEdge(b, b1)
        g.AddEdge(b, b2)

        b21 = GraphNode('B21', 0, 0)
        b22 = GraphNode('B22', 0, 0, 100, 200)
        g.AddEdge(b2, b21)
        g.AddEdge(b2, b22)

        c = GraphNode('c', 0, 0)
        c1 = GraphNode('c1', 0, 0)
        c2 = GraphNode('c2', 0, 0)
        c3 = GraphNode('c3', 0, 0)
        c4 = GraphNode('c4', 0, 0)
        c5 = GraphNode('c5', 0, 0, 60, 120)
        g.AddEdge(c, c1)
        g.AddEdge(c, c2)
        g.AddEdge(c, c3)
        g.AddEdge(c, c4)
        g.AddEdge(c, c5)
        g.AddEdge(a, c)
        
        g.AddEdge(b2, c)
        g.AddEdge(b2, c5)
        g.AddEdge(a, c5)

        layouter = GraphLayoutSpring(g)
        layouter.layout()
        
        for node in g.nodes:
            print node.id, (node.layoutPosX, node.layoutPosY)
        
        ## ==========================================
        
        # apply sizer
        self.SetSizer(sizer)
        self.SetAutoLayout(1)
        self.Show(1)

        ## ==========================================

        renderer = GraphRendererOgl(g, canvas);
        renderer.draw();
        
        diagram.ShowAll( 1 )
        

app = wx.PySimpleApp()
ogl.OGLInitialize()
frame = AppFrame()
app.MainLoop()
app.Destroy()
