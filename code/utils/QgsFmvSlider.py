from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QSlider , QStyleOptionSlider, QStyle
from QGIS_FMV.utils.QgsFmvUtils import qmouse_pos

class QgsFmvSlider(QSlider):

    mousePressed = pyqtSignal(int)
         
    def mousePressEvent(self, event):
        super(QgsFmvSlider, self).mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.pixelPosToRangeValue(qmouse_pos(event))
            self.setValue(val)
            self.mousePressed.emit(val)
            
    def pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderGroove, self)
        sr = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self)

        if self.orientation() == Qt.Orientation.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == Qt.Orientation.Horizontal else pr.y()
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin,
                                               sliderMax - sliderMin, opt.upsideDown)