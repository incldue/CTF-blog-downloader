import os
import platform
import subprocess
import threading
import tkinter as tk
import webbrowser
from collections import Counter
from tkinter import filedialog, messagebox, ttk

from browser_utils import detect_browser_executable, resolve_browser_executable
from downloader import download_as_md
from puller import concurrent_search


class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("博客下载助手 (目前支持CSDN/博客园/先知社区)")
        self.root.geometry("1160x760")
        self.root.minsize(1020, 660)

        self.search_results = []
        self.result_lookup = {}
        self.filtered_results = []
        self.search_in_progress = False
        self.active_downloads = 0
        self.last_save_dir = ""

        self.status_var = tk.StringVar(value="就绪")
        self.summary_var = tk.StringVar(value="暂无搜索结果")
        self.selection_var = tk.StringVar(value="未选择文章")
        self.filter_var = tk.StringVar(value="全部平台")

        self.configure_styles()
        self.setup_ui()

    def configure_styles(self):
        self.root.configure(bg="#f5f5f7")
        style = ttk.Style()
        style.configure("Toolbar.TButton", padding=(10, 6))
        style.configure("Primary.TButton", padding=(12, 6))
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("Helvetica Neue", 12, "normal"))

    def setup_ui(self):
        container = tk.Frame(self.root, bg="#f5f5f7", padx=18, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(container, bg="#f5f5f7")
        header.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            header,
            text="博客下载助手",
            bg="#f5f5f7",
            fg="#1d1d1f",
            font=("Helvetica Neue", 24, "normal"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="不仅限于CTFer,日常查资料也很方便",
            bg="#f5f5f7",
            fg="#6e6e73",
            font=("Helvetica Neue", 12),
        ).pack(anchor="w", pady=(4, 0))

        toolbar_card = tk.Frame(
            container,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#e5e5ea",
            bd=0,
            padx=16,
            pady=14,
        )
        toolbar_card.pack(fill=tk.X, pady=(0, 12))

        first_row = tk.Frame(toolbar_card, bg="#ffffff")
        first_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(first_row, text="关键词").pack(side=tk.LEFT)
        self.kw_entry = ttk.Entry(first_row, width=34)
        self.kw_entry.pack(side=tk.LEFT, padx=(8, 16))
        self.kw_entry.bind("<Return>", lambda _event: self.on_search_click())

        ttk.Label(first_row, text="搜索页数").pack(side=tk.LEFT)
        self.pg_entry = ttk.Spinbox(first_row, from_=1, to=99, width=6)
        self.pg_entry.set("1")
        self.pg_entry.pack(side=tk.LEFT, padx=(8, 16))

        ttk.Label(first_row, text="平台筛选").pack(side=tk.LEFT)
        self.filter_combo = ttk.Combobox(
            first_row,
            textvariable=self.filter_var,
            values=("全部平台", "CSDN", "博客园", "先知社区"),
            state="readonly",
            width=12,
        )
        self.filter_combo.pack(side=tk.LEFT, padx=(8, 16))
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filter())

        self.search_button = ttk.Button(first_row, text="搜索", style="Primary.TButton", command=self.on_search_click)
        self.search_button.pack(side=tk.LEFT)
        ttk.Button(first_row, text="清空", style="Toolbar.TButton", command=self.clear_results).pack(side=tk.LEFT, padx=(8, 0))

        second_row = tk.Frame(toolbar_card, bg="#ffffff")
        second_row.pack(fill=tk.X)
        ttk.Label(second_row, text="浏览器路径").pack(side=tk.LEFT)
        self.browser_entry = ttk.Entry(second_row)
        self.browser_entry.insert(0, detect_browser_executable())
        self.browser_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Button(second_row, text="选择", style="Toolbar.TButton", command=self.select_browser).pack(side=tk.LEFT)
        ttk.Button(second_row, text="自动检测", style="Toolbar.TButton", command=self.autofill_browser).pack(side=tk.LEFT, padx=(8, 0))

        meta_row = tk.Frame(container, bg="#f5f5f7")
        meta_row.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            meta_row,
            text="浏览器路径可以留空。留空时将使用 Playwright 自带 Chromium。",
            bg="#f5f5f7",
            fg="#6e6e73",
            font=("Helvetica Neue", 11),
        ).pack(side=tk.LEFT)

        action_frame = tk.Frame(container, bg="#f5f5f7")
        action_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(action_frame, text="全选", style="Toolbar.TButton", command=self.select_all_results).pack(side=tk.LEFT)
        ttk.Button(action_frame, text="反选", style="Toolbar.TButton", command=self.invert_selection).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_frame, text="打开文章", style="Toolbar.TButton", command=self.open_selected_article).pack(side=tk.LEFT, padx=(8, 0))
        self.download_button = ttk.Button(
            action_frame,
            text="导出 Markdown",
            style="Primary.TButton",
            command=self.on_download_click,
        )
        self.download_button.pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="打开导出目录", style="Toolbar.TButton", command=self.open_last_save_dir).pack(side=tk.RIGHT, padx=(0, 8))

        info_frame = tk.Frame(container, bg="#f5f5f7")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            info_frame,
            textvariable=self.summary_var,
            bg="#f5f5f7",
            fg="#6e6e73",
            font=("Helvetica Neue", 11),
        ).pack(side=tk.LEFT)
        tk.Label(
            info_frame,
            textvariable=self.selection_var,
            bg="#f5f5f7",
            fg="#6e6e73",
            font=("Helvetica Neue", 11),
        ).pack(side=tk.RIGHT)

        table_card = tk.Frame(
            container,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#e5e5ea",
            bd=0,
            padx=12,
            pady=12,
        )
        table_card.pack(fill=tk.BOTH, expand=True)

        table_header = tk.Frame(table_card, bg="#ffffff")
        table_header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            table_header,
            text="文章",
            bg="#ffffff",
            fg="#1d1d1f",
            font=("Helvetica Neue", 14, "normal"),
        ).pack(side=tk.LEFT)

        tree_container = tk.Frame(table_card, bg="#ffffff")
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("site", "title", "url", "status")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("site", text="平台")
        self.tree.heading("title", text="标题")
        self.tree.heading("url", text="文章链接")
        self.tree.heading("status", text="状态")
        self.tree.column("site", width=90, anchor=tk.CENTER, stretch=False)
        self.tree.column("title", width=420)
        self.tree.column("url", width=460)
        self.tree.column("status", width=120, anchor=tk.CENTER, stretch=False)
        self.tree.tag_configure("ready", foreground="#1d1d1f")
        self.tree.tag_configure("done", foreground="#2d6a4f")
        self.tree.tag_configure("failed", foreground="#b00020")
        self.tree.tag_configure("loading", foreground="#6e6e73")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_selection_summary())
        self.tree.bind("<Double-1>", lambda _event: self.open_selected_article())

        bottom_bar = tk.Frame(container, bg="#f5f5f7")
        bottom_bar.pack(fill=tk.X, pady=(12, 0))

        self.progress = ttk.Progressbar(bottom_bar, mode="indeterminate", length=220)
        self.progress.pack(side=tk.LEFT)
        tk.Label(
            bottom_bar,
            textvariable=self.status_var,
            bg="#f5f5f7",
            fg="#6e6e73",
            font=("Helvetica Neue", 11),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def set_busy(self, busy, text=None):
        def update_ui():
            if text:
                self.status_var.set(text)
            if busy:
                self.progress.start(10)
                self.search_button.state(["disabled"])
                self.download_button.state(["disabled"])
            else:
                self.progress.stop()
                self.search_button.state(["!disabled"])
                self.download_button.state(["!disabled"])

        self.root.after(0, update_ui)

    def autofill_browser(self):
        detected = detect_browser_executable()
        self.browser_entry.delete(0, tk.END)
        self.browser_entry.insert(0, detected)
        self.set_status("已自动检测浏览器路径" if detected else "未检测到本机浏览器，可留空使用 Playwright Chromium")

    def select_browser(self):
        file_path = filedialog.askopenfilename(filetypes=[("All files", "*")])
        if file_path:
            self.browser_entry.delete(0, tk.END)
            self.browser_entry.insert(0, file_path)

    def on_search_click(self):
        if self.search_in_progress:
            messagebox.showinfo("提示", "当前正在搜索，请稍候。")
            return

        kw = self.kw_entry.get().strip()
        page_text = self.pg_entry.get().strip()
        browser_path = self.browser_entry.get().strip()

        if not kw:
            messagebox.showwarning("提示", "请输入关键词！")
            return

        try:
            pages = int(page_text)
            if pages < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "搜索页数必须是大于 0 的整数！")
            return

        if browser_path and not resolve_browser_executable(browser_path):
            messagebox.showwarning("提示", "浏览器路径无效，请重新选择，或留空使用 Playwright Chromium。")
            return

        self.search_in_progress = True
        self.clear_tree()
        self.tree.insert("", tk.END, iid="__loading__", values=("系统", "正在搜索文章，请稍候...", "", "SEARCHING"), tags=("loading",))
        self.summary_var.set("正在搜索中...")
        self.selection_var.set("未选择文章")
        self.set_busy(True, "开始搜索文章...")

        threading.Thread(target=lambda: self.perform_search(kw, pages, browser_path), daemon=True).start()

    def perform_search(self, keyword, pages, browser_path):
        try:
            results = concurrent_search(keyword, pages, browser_path, on_status=self.set_status)
            self.root.after(0, lambda: self.handle_search_results(results))
        except Exception as e:
            self.root.after(0, lambda: self.handle_search_error(str(e)))

    def handle_search_results(self, results):
        self.search_in_progress = False
        self.search_results = []
        self.result_lookup = {}

        for index, item in enumerate(results, start=1):
            result = {
                "id": str(index),
                "site": item["site"],
                "title": item["title"],
                "url": item["url"],
                "status": "就绪",
            }
            self.search_results.append(result)
            self.result_lookup[result["id"]] = result

        self.apply_filter()
        self.set_busy(False, f"搜索完成，共找到 {len(self.search_results)} 篇文章")

    def handle_search_error(self, detail):
        self.search_in_progress = False
        self.clear_tree()
        self.set_busy(False, f"搜索失败：{detail}")
        messagebox.showerror("搜索失败", detail)

    def clear_tree(self):
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

    def clear_results(self):
        if self.search_in_progress or self.active_downloads:
            messagebox.showinfo("提示", "当前有任务在运行，请完成后再清空。")
            return

        self.search_results = []
        self.result_lookup = {}
        self.filtered_results = []
        self.clear_tree()
        self.summary_var.set("暂无搜索结果")
        self.selection_var.set("未选择文章")
        self.set_status("已清空结果")

    def apply_filter(self):
        selected_site = self.filter_var.get()
        if selected_site == "全部平台":
            self.filtered_results = list(self.search_results)
        else:
            self.filtered_results = [item for item in self.search_results if item["site"] == selected_site]

        self.render_table()
        self.update_summary()
        self.update_selection_summary()

    def render_table(self):
        self.clear_tree()
        if not self.filtered_results:
            self.tree.insert("", tk.END, iid="__empty__", values=("系统", "当前筛选条件下没有结果", "", "EMPTY"), tags=("loading",))
            return

        for item in self.filtered_results:
            status = item["status"]
            tag = "ready"
            if status == "完成":
                tag = "done"
            elif status == "失败":
                tag = "failed"
            elif "下载中" in status:
                tag = "loading"

            self.tree.insert(
                "",
                tk.END,
                iid=item["id"],
                values=(item["site"], item["title"], item["url"], status),
                tags=(tag,),
            )

    def update_summary(self):
        if not self.search_results:
            self.summary_var.set("暂无搜索结果")
            return

        counts = Counter(item["site"] for item in self.filtered_results)
        count_text = " / ".join(f"{site} {count}" for site, count in sorted(counts.items()))
        if not count_text:
            count_text = "当前筛选下无结果"
        self.summary_var.set(
            f"总计 {len(self.search_results)} 篇，当前显示 {len(self.filtered_results)} 篇"
            + (f"（{count_text}）" if count_text else "")
        )

    def update_selection_summary(self):
        selected_ids = [item_id for item_id in self.tree.selection() if item_id in self.result_lookup]
        if not selected_ids:
            self.selection_var.set("未选择文章")
            return

        self.selection_var.set(f"已选择 {len(selected_ids)} 篇文章")

    def get_selected_result_ids(self):
        return [item_id for item_id in self.tree.selection() if item_id in self.result_lookup]

    def select_all_results(self):
        visible_ids = [item["id"] for item in self.filtered_results]
        if visible_ids:
            self.tree.selection_set(visible_ids)
            self.update_selection_summary()

    def invert_selection(self):
        visible_ids = [item["id"] for item in self.filtered_results]
        if not visible_ids:
            return

        current = set(self.tree.selection())
        inverted = [item_id for item_id in visible_ids if item_id not in current]
        self.tree.selection_set(inverted)
        self.update_selection_summary()

    def open_selected_article(self):
        selected_ids = self.get_selected_result_ids()
        if not selected_ids:
            messagebox.showinfo("提示", "请先选择一篇文章。")
            return

        url = self.result_lookup[selected_ids[0]]["url"]
        webbrowser.open(url)
        self.set_status("已在系统浏览器中打开文章")

    def open_last_save_dir(self):
        if not self.last_save_dir or not os.path.isdir(self.last_save_dir):
            messagebox.showinfo("提示", "还没有可打开的导出目录。")
            return

        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", self.last_save_dir])
            elif system == "Windows":
                os.startfile(self.last_save_dir)
            else:
                subprocess.Popen(["xdg-open", self.last_save_dir])
            self.set_status("已打开导出目录")
        except Exception as e:
            messagebox.showerror("打开目录失败", str(e))

    def on_download_click(self):
        selected_ids = self.get_selected_result_ids()
        if not selected_ids:
            messagebox.showinfo("提示", "请在列表中选择所需要下载的文章。")
            return

        if self.active_downloads:
            messagebox.showinfo("提示", "当前已有下载任务在运行，请稍候。")
            return

        save_dir = filedialog.askdirectory()
        if not save_dir:
            return

        browser_path = self.browser_entry.get().strip()
        if browser_path and not resolve_browser_executable(browser_path):
            messagebox.showwarning("提示", "浏览器路径无效，请重新选择，或留空使用 Playwright Chromium。")
            return

        self.last_save_dir = save_dir
        self.active_downloads = len(selected_ids)
        self.set_busy(True, f"开始下载，共 {self.active_downloads} 篇文章")

        for item_id in selected_ids:
            result = self.result_lookup[item_id]
            result["status"] = "下载中..."
            if self.tree.exists(item_id):
                self.tree.item(item_id, values=(result["site"], result["title"], result["url"], result["status"]), tags=("loading",))

            threading.Thread(
                target=self.download_task,
                args=(item_id, result["title"], result["url"], save_dir, browser_path),
                daemon=True,
            ).start()

    def build_output_path(self, save_dir, title):
        safe_title = "".join([char for char in title if char.isalnum() or char in " -_"]).strip() or "untitled"
        file_path = os.path.join(save_dir, f"{safe_title}.md")
        counter = 2
        while os.path.exists(file_path):
            file_path = os.path.join(save_dir, f"{safe_title}_{counter}.md")
            counter += 1
        return file_path

    def download_task(self, item_id, title, url, save_dir, browser_path):
        file_path = self.build_output_path(save_dir, title)
        success, detail = download_as_md(url, file_path, browser_path)

        def finish():
            result = self.result_lookup.get(item_id)
            if result:
                result["status"] = "完成" if success else "失败"

            if self.tree.exists(item_id) and result:
                tag = "done" if success else "failed"
                self.tree.item(item_id, values=(result["site"], result["title"], result["url"], result["status"]), tags=(tag,))

            self.active_downloads -= 1
            if success:
                self.status_var.set(f"下载完成：{os.path.basename(file_path)}")
            else:
                self.status_var.set(f"下载失败：{title}")
                messagebox.showwarning("下载失败", f"{title}\n\n{detail}")

            if self.active_downloads <= 0:
                self.active_downloads = 0
                self.set_busy(False, "批量下载已结束")

            self.update_summary()
            self.update_selection_summary()

        self.root.after(0, finish)
