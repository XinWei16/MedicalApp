import sys
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QMessageBox, QFrame, QGridLayout,
                             QScrollArea, QSizePolicy, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QEvent
from docx import Document


# --- 1. 核心修改：支持多选且点击稳定的下拉框组件 ---
class MultiSelectComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("可多选...")

        # 关键修改点 A：让输入框对鼠标点击透明，这样点击文字/空白处会直接由底层的 ComboBox 处理
        self.lineEdit().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.list_widget = QListWidget()
        self.setModel(self.list_widget.model())
        self.setView(self.list_widget)

        # 关键修改点 B：拦截视图视口事件，处理勾选逻辑
        self.view().viewport().installEventFilter(self)
        self.model().dataChanged.connect(self.update_text)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def eventFilter(self, widget, event):
        # 处理列表内部点击勾选逻辑
        if widget == self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            item = self.list_widget.item(index.row())
            if item:
                item.setCheckState(
                    Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            return True
        return super().eventFilter(widget, event)

    # 关键修改点 C：接管鼠标释放事件。
    # 点击空白处和点击小三角现在都会触发这里，实现稳定的开关切换
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.view().isVisible():
                self.hidePopup()
            else:
                self.showPopup()
        else:
            super().mouseReleaseEvent(event)

    # 关键修改点 D：拦截鼠标按下事件，防止系统默认逻辑导致“弹出后立即关闭”的闪退
    def mousePressEvent(self, event):
        pass

        # 需求：禁用滚轮控制选项

    def wheelEvent(self, e):
        if not self.view().isVisible():
            e.ignore()  # 未展开时，滚轮无效
        else:
            # 展开时，允许滚轮滚动内部列表内容
            self.view().verticalScrollBar().wheelEvent(e)

    def addItems(self, texts):
        for text in texts:
            item = QListWidgetItem(text)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)

    def update_text(self):
        selected = [self.list_widget.item(i).text() for i in range(self.list_widget.count())
                    if self.list_widget.item(i).checkState() == Qt.CheckState.Checked]
        self.lineEdit().setText(", ".join(selected))

    def currentText(self):
        return self.lineEdit().text()


# --- 2. 普通单选框也禁用滚轮 ---
class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, e):
        if not self.view().isVisible():
            e.ignore()
        else:
            super().wheelEvent(e)


# --- 3. 主界面程序 ---
class MedicalApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("口腔种植病历生成器 v2.3 - 交互优化版")
        self.setMinimumSize(950, 850)
        self.init_ui()
        self.apply_dark_style()

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)

        main_bg = QWidget()
        scroll.setWidget(main_bg)
        global_layout = QVBoxLayout(main_bg)
        global_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        content_wrapper = QFrame()
        content_wrapper.setFixedWidth(850)
        global_layout.addWidget(content_wrapper)

        layout = QVBoxLayout(content_wrapper)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 标题
        header = QVBoxLayout()
        title = QLabel("口腔种植病历模板生成系统")
        title.setObjectName("MainTitle")
        subtitle = QLabel("3D Automation Engine | 自动化病历填充引擎")
        subtitle.setObjectName("SubTitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 文件配置区
        file_section = QFrame()
        file_section.setObjectName("SectionCard")
        file_grid = QGridLayout(file_section)
        file_grid.setContentsMargins(20, 20, 20, 20)

        self.template_path = QLineEdit()
        self.template_path.setPlaceholderText("尚未选择模板文件...")
        self.template_path.setReadOnly(True)
        btn_browse = QPushButton("选择模板")
        btn_browse.setFixedSize(95, 35)
        btn_browse.clicked.connect(self.get_template)
        self.output_name = QLineEdit("生成_口腔种植病历.docx")

        file_grid.addWidget(QLabel("DOCX 模板:"), 0, 0)
        file_grid.addWidget(self.template_path, 0, 1)
        file_grid.addWidget(btn_browse, 0, 2)
        file_grid.addWidget(QLabel("保存名称:"), 1, 0)
        file_grid.addWidget(self.output_name, 1, 1, 1, 2)
        layout.addWidget(file_section)

        # 表单区
        form_section = QFrame()
        form_section.setObjectName("SectionCard")
        form_grid = QGridLayout(form_section)
        form_grid.setContentsMargins(25, 30, 25, 30)
        form_grid.setSpacing(20)

        self.inputs = {}

        # 填充各项控件
        self.add_form_item(form_grid, "1. 病情描述", "desc", "例如：牙缺失一年以上", 0, 0, 1, 2)

        brands = ["卡瓦盛邦", "士卓曼(亲水)", "士卓曼(非亲水)", "韩国DIO", "Nobel", "Nobel cc", "Nobel pmc",
                  "Nobel pcc", "Nobel active"]
        self.add_multi_combo_item(form_grid, "2. 植体品牌 (多选)", "brand", brands, 1, 0)

        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("YYYY-MM-DD")
        self.date_input.textChanged.connect(self.format_date)
        self.add_custom_item(form_grid, "4. 种植日期", self.date_input, "date", 1, 1)

        self.add_form_item(form_grid, "3-1. 牙位", "tooth_pos", "如: 46", 2, 0)
        self.add_form_item(form_grid, "3-2. 植体型号", "tooth_model", "如: 4.3x10mm", 2, 1)

        self.add_multi_combo_item(form_grid, "5. 颌位选择 (多选)", "jaw", ["上", "下"], 3, 0)
        self.add_multi_combo_item(form_grid, "6. 手术类型 (多选)", "op_type", ["种植", "上颌窦内提升", "上颌窦外提升"],
                                  3, 1)

        self.add_combo_item(form_grid, "7. 种植体个数", "count", [str(i) for i in range(1, 21)], 4, 0)
        self.add_multi_combo_item(form_grid, "8. 冠桥类型 (多选)", "bridge",
                                  ["单冠", "连冠", "上半口桥架", "下半口桥架", "全口桥架"], 4, 1)

        self.add_combo_item(form_grid, "9_1. 高压 (mmHg)", "h_pressure", [str(i) for i in range(110, 121)], 5, 0)
        self.add_combo_item(form_grid, "9_2. 低压 (mmHg)", "l_pressure", [str(i) for i in range(70, 81)], 5, 1)
        self.add_combo_item(form_grid, "10. 心率 (次/分)", "rate", [str(i) for i in range(60, 101)], 6, 0)

        self.s_time_input = QLineEdit();
        self.s_time_input.setPlaceholderText("HH:MM")
        self.s_time_input.textChanged.connect(lambda t: self.format_time(self.s_time_input, t))
        self.add_custom_item(form_grid, "11_1. 开始时间", self.s_time_input, "s_time", 6, 1)

        self.e_time_input = QLineEdit();
        self.e_time_input.setPlaceholderText("HH:MM")
        self.e_time_input.textChanged.connect(lambda t: self.format_time(self.e_time_input, t))
        self.add_custom_item(form_grid, "11_2. 结束时间", self.e_time_input, "e_time", 7, 0)

        self.add_combo_item(form_grid, "12. 牙龈厚度", "thickness", [f"{i}mm" for i in range(2, 11)], 7, 1)
        self.add_combo_item(form_grid, "13. 骨质分类", "bone", ["I 类骨", "II 类骨", "III 类骨", "IV 类骨"], 8, 0, 1, 2)

        layout.addWidget(form_section)

        # 按钮
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_exit = QPushButton("退出程序")
        btn_exit.setFixedSize(140, 50);
        btn_exit.setObjectName("ExitButton")
        btn_exit.clicked.connect(self.close)

        btn_generate = QPushButton("生成并导出 Word 文档")
        btn_generate.setFixedHeight(50);
        btn_generate.setObjectName("GenerateButton")
        btn_generate.clicked.connect(self.generate_word)

        btn_layout.addWidget(btn_exit)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(btn_generate)
        layout.addWidget(btn_container)

    # --- 辅助方法 ---
    def add_form_item(self, grid, label, key, placeholder, r, c, rs=1, cs=1):
        vbox = QVBoxLayout();
        vbox.setSpacing(8)
        edit = QLineEdit();
        edit.setPlaceholderText(placeholder)
        vbox.addWidget(QLabel(label));
        vbox.addWidget(edit)
        self.inputs[key] = edit
        grid.addLayout(vbox, r, c, rs, cs)

    def add_combo_item(self, grid, label, key, items, r, c, rs=1, cs=1):
        vbox = QVBoxLayout();
        vbox.setSpacing(8)
        combo = NoWheelComboBox()
        combo.addItems(items)
        vbox.addWidget(QLabel(label));
        vbox.addWidget(combo)
        self.inputs[key] = combo
        grid.addLayout(vbox, r, c, rs, cs)

    def add_multi_combo_item(self, grid, label, key, items, r, c, rs=1, cs=1):
        vbox = QVBoxLayout();
        vbox.setSpacing(8)
        combo = MultiSelectComboBox()
        combo.addItems(items)
        vbox.addWidget(QLabel(label));
        vbox.addWidget(combo)
        self.inputs[key] = combo
        grid.addLayout(vbox, r, c, rs, cs)

    def add_custom_item(self, grid, label, widget, key, r, c):
        vbox = QVBoxLayout();
        vbox.setSpacing(8)
        vbox.addWidget(QLabel(label));
        vbox.addWidget(widget)
        self.inputs[key] = widget
        grid.addLayout(vbox, r, c)

    def format_date(self, text):
        self.date_input.blockSignals(True)
        raw = text.replace("-", "")[:8]
        res = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}".strip("-") if len(raw) > 4 else raw
        self.date_input.setText(res)
        self.date_input.blockSignals(False)

    def format_time(self, widget, text):
        widget.blockSignals(True)
        raw = text.replace(":", "")[:4]
        res = f"{raw[:2]}:{raw[2:4]}".strip(":") if len(raw) > 2 else raw
        widget.setText(res)
        widget.blockSignals(False)

    def get_template(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择模板", "", "Word Files (*.docx)")
        if file: self.template_path.setText(file)

    def generate_word(self):
        path = self.template_path.text()
        if not path:
            QMessageBox.warning(self, "错误", "请先选择 Word 模板文件！")
            return
        try:
            doc = Document(path)
            vals = {k: (v.currentText() if isinstance(v, QComboBox) else v.text()) for k, v in self.inputs.items()}

            # 自动计算逻辑
            d1 = d2 = num2 = ""
            try:
                base_dt = datetime.strptime(vals['date'], "%Y-%m-%d")
                d1 = (base_dt + timedelta(days=150)).strftime("%Y-%m-%d")
                d2 = (base_dt + timedelta(days=158)).strftime("%Y-%m-%d")
                num2 = str(int(vals['count']) * 2)
            except:
                pass

            rmap = {
                "{{description}}": vals['desc'], "{{brand}}": vals['brand'], "{{y_position}}": vals['tooth_pos'],
                "{{model}}": vals['tooth_model'], "{{date}}": vals['date'], "{{date1}}": d1, "{{date2}}": d2,
                "{{e_position}}": vals['jaw'], "{{surgery}}": vals['op_type'], "{{number}}": vals['count'],
                "{{number2}}": num2, "{{Crown}}": vals['bridge'], "{{h_pressure}}": vals['h_pressure'],
                "{{l_pressure}}": vals['l_pressure'], "{{rate}}": vals['rate'], "{{s_time}}": vals['s_time'],
                "{{o_time}}": vals['e_time'], "{{thickness}}": vals['thickness'], "{{bone}}": vals['bone']
            }

            for p in doc.paragraphs:
                for k, v in rmap.items():
                    if k in p.text: p.text = p.text.replace(k, v)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for k, v in rmap.items():
                            if k in cell.text: cell.text = cell.text.replace(k, v)

            save_path, _ = QFileDialog.getSaveFileName(self, "导出病历", self.output_name.text(), "Word Files (*.docx)")
            if save_path:
                doc.save(save_path)
                QMessageBox.information(self, "生成完毕", "病历文件已成功保存！")
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"错误提示: {str(e)}")

    def apply_dark_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1A1A21; font-family: "Segoe UI", "Microsoft YaHei UI"; }
            #MainTitle { color: #FFFFFF; font-size: 28px; font-weight: 800; }
            #SubTitle { color: #6A6A80; font-size: 14px; margin-bottom: 5px; }
            #SectionCard { background-color: #242430; border-radius: 15px; border: 1px solid #3A3A4A; }
            QLabel { color: #A0A0B5; font-size: 13px; font-weight: bold; }
            QLineEdit, QComboBox, QListWidget { 
                background-color: #1C1C26; border: 1px solid #12121A; border-radius: 8px; 
                padding: 10px; color: #F0F0F0; font-size: 14px;
            }
            QListWidget::item { height: 35px; padding-left: 10px; }
            QListWidget::item:hover { background-color: #3498DB; }
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4A4A5A, stop:1 #2D2D3D);
                color: #E0E0E0; border-radius: 8px; font-weight: bold;
            }
            #GenerateButton { background: #2980B9; color: white; border-bottom: 4px solid #1F618D; }
            #ExitButton:hover { background: #C0392B; color: white; }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MedicalApp()
    window.showFullScreen()
    sys.exit(app.exec())