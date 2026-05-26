from io import StringIO
import pandas as pd
import requests
from bs4 import BeautifulSoup
from collections import deque
import time
import os


# ===================== 数据结构1：队列（FIFO）- 通用任务调度器 =====================
# 核心思想：先进先出，按添加顺序依次处理任务
# 应用场景：多页面爬取、分页爬取、不同数据类型的批量处理
class TaskQueue:
    def __init__(self):
        # 使用双端队列deque实现，入队/出队O(1)，比Python列表高效100倍以上
        self.queue = deque()

    def enqueue(self, item):
        """入队：将任务添加到队列尾部"""
        self.queue.append(item)

    def dequeue(self):
        """出队：从队列头部取出并返回任务"""
        return self.queue.popleft() if not self.is_empty() else None

    def is_empty(self):
        """判断队列是否为空"""
        return len(self.queue) == 0

    def size(self):
        """返回队列中任务数量"""
        return len(self.queue)

    def clear(self):
        """清空队列"""
        self.queue.clear()


# ===================== 数据结构2：栈（LIFO）- 通用HTML表格解析器 =====================
# 核心思想：后进先出，完美匹配HTML嵌套标签的解析逻辑
# 应用场景：任何HTML表格解析、XML解析、表达式求值、括号匹配
class TableParseStack:
    def __init__(self):
        self.stack = []

    def push(self, value):
        """入栈：将元素压入栈顶"""
        self.stack.append(value)

    def pop(self):
        """出栈：从栈顶取出并返回元素"""
        return self.stack.pop() if not self.is_empty() else None

    def peek(self):
        """查看栈顶元素但不取出"""
        return self.stack[-1] if not self.is_empty() else None

    def is_empty(self):
        """判断栈是否为空"""
        return len(self.stack) == 0

    def size(self):
        """返回栈中元素数量"""
        return len(self.stack)


# ===================== 同花顺股票数据爬虫（纯数据结构实现）=====================
class THSStockCrawler:
    def __init__(self):
        # 初始化会话，保持Cookie连接
        self.session = requests.Session()
        # 初始化任务队列
        self.task_queue = TaskQueue()
        # 请求头，模拟真实浏览器
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://data.10jqka.com.cn/"
        }
        # 数据保存目录
        self.save_dir = "同花顺股票数据"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        # 预访问首页，初始化会话
        self._init_session()

    def _init_session(self):
        """初始化会话，获取必要的Cookie"""
        try:
            self.session.get("http://data.10jqka.com.cn", headers=self.headers, timeout=10)
            time.sleep(0.5)
            print("✅ 会话初始化成功")
        except Exception as e:
            print(f"❌ 会话初始化失败：{e}")

    def add_task(self, url, data_type, page=1):
        """
        添加爬取任务到队列
        :param url: 爬取地址
        :param data_type: 数据类型（用于保存文件命名）
        :param page: 页码
        """
        task = {
            "url": url,
            "data_type": data_type,
            "page": page
        }
        self.task_queue.enqueue(task)
        print(f"📥 添加任务：{data_type} 第{page}页（当前队列任务数：{self.task_queue.size()}）")

    def parse_table_with_stack(self, html):
        """
        使用栈解析HTML表格（通用版，支持所有同花顺表格）
        解析算法：
        1. 栈中存储(标签类型, 元素对象)元组
        2. 遇到table：将所有tr逆序入栈（保证弹出顺序为正序）
        3. 遇到tr：先入栈行结束标记，再将所有td/th逆序入栈
        4. 遇到td/th：提取文本存入当前行
        5. 遇到行结束标记：将完整行存入结果集
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            print("❌ 未找到表格元素")
            return []

        stack = TableParseStack()
        result = []
        current_row = []

        # 将根表格元素入栈
        stack.push(("table", table))

        while not stack.is_empty():
            tag_type, elem = stack.pop()

            if tag_type == "table":
                # 找到所有行，逆序入栈（栈后进先出，弹出时恢复正序）
                all_trs = table.find_all("tr")
                for tr in reversed(all_trs):
                    stack.push(("tr", tr))

            elif tag_type == "tr":
                # 重置当前行
                current_row = []
                # 关键：先入栈行结束标记，再入栈单元格
                # 这样单元格会先被处理，最后触发行结束
                stack.push(("end_row", None))
                # 找到所有单元格，逆序入栈
                all_tds = elem.find_all(["td", "th"])
                for td in reversed(all_tds):
                    stack.push(("cell", td))

            elif tag_type == "cell":
                # 提取单元格文本，去除空白字符
                cell_text = elem.get_text(strip=True)
                current_row.append(cell_text)

            elif tag_type == "end_row":
                # 行结束，将当前行添加到结果集（过滤空行）
                if current_row and any(cell.strip() for cell in current_row):
                    result.append(current_row)

        return result

    def _get_total_pages(self, html):
        """
        使用栈解析获取总页数（展示栈的另一种应用）
        """
        soup = BeautifulSoup(html, "lxml")
        page_info = soup.find("span", class_="page_info")
        if page_info:
            text = page_info.get_text(strip=True)
            if "/" in text:
                return int(text.split("/")[-1])
        return 1

    def run(self):
        """执行所有爬取任务"""
        all_results = {}
        print(f"\n🚀 开始执行爬取任务，共{self.task_queue.size()}个任务")

        while not self.task_queue.is_empty():
            current_task = self.task_queue.dequeue()
            url = current_task["url"]
            data_type = current_task["data_type"]
            page = current_task["page"]

            print(f"\n📤 正在处理：{data_type} 第{page}页")
            print(f"   地址：{url}")

            try:
                # 发送请求
                response = self.session.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()

                # 第一页时获取总页数并添加后续任务到队列
                if page == 1:
                    total_pages = self._get_total_pages(response.text)
                    print(f"   发现总页数：{total_pages}")
                    for p in range(2, min(total_pages + 1, 6)):  # 限制最多爬5页，避免请求过多
                        self.add_task(f"{url}page/{p}/", data_type, p)

                # 纯栈解析表格数据
                table_data = self.parse_table_with_stack(response.text)

                if table_data and len(table_data) > 1:
                    # 转换为DataFrame
                    df = pd.DataFrame(table_data[1:], columns=table_data[0])

                    # 合并到结果集
                    if data_type not in all_results:
                        all_results[data_type] = df
                    else:
                        all_results[data_type] = pd.concat([all_results[data_type], df], ignore_index=True)

                    print(f"✅ 处理成功，获取{len(df)}条记录")
                else:
                    print(f"⚠️  该页无数据")

                # 控制请求频率，避免被封IP
                time.sleep(1)

            except Exception as e:
                print(f"❌ 处理异常：{e}")

        # 保存所有数据
        print("\n📦 开始保存数据...")
        for data_type, df in all_results.items():
            filename = f"{self.save_dir}/{data_type}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"   ✅ {data_type}：{len(df)}条记录，已保存到 {filename}")

        print("\n🎉 所有任务执行完成！")
        return all_results


# ===================== 主程序：一键爬取多种股票数据 =====================
if __name__ == "__main__":
    # 创建爬虫实例
    crawler = THSStockCrawler()

    # ===================== 添加你需要爬取的股票数据任务 =====================
    # 1. 行业资金流数据（你之前的需求）
    crawler.add_task("http://data.10jqka.com.cn/funds/hyzjl/", "行业资金流")

    # 2. 个股资金流数据（实时资金流向）
    crawler.add_task("http://data.10jqka.com.cn/funds/ggzjl/", "个股资金流")

    # 3. 业绩预告数据（公司基本面）
    crawler.add_task("http://data.10jqka.com.cn/financial/yjyg/", "业绩预告")

    # 执行所有任务
    results = crawler.run()

    # 数据预览
    if results:
        print("\n" + "=" * 50)
        print("📊 数据预览")
        print("=" * 50)

        for data_type, df in results.items():
            print(f"\n【{data_type}】（前5行）：")
            print(df.head(5).to_string(index=False))