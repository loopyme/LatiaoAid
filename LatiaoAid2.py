from dataclasses import dataclass, field
from datetime import datetime, timedelta
from queue import PriorityQueue
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, \
    StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from Logger import Logger

WEBDRIVER_PATH = '/usr/local/bin/geckodriver'
BASE_URL = "https://passport.bilibili.com/login"
YJZ_CHANNEL = "https://live.bilibili.com/528"


@dataclass(order=True)
class Channel:
    link: str = field(compare=False)
    caster: str = field(compare=False)
    due_time: datetime


class LatiaoAid:
    def __init__(self):
        self.driver = webdriver.Firefox(executable_path=WEBDRIVER_PATH)
        self.waiting_list = []
        self.queue = PriorityQueue()
        self.set = set()
        self.base_tab = None
        self.loot_tab = None

    def delete_element(self, element):
        self.driver.execute_script("""
        var element = arguments[0];
        element.parentNode.removeChild(element);
        """, element)

    def login(self):
        self.driver.get(BASE_URL)
        WebDriverWait(self.driver, 99999).until(ec.url_to_be("https://www.bilibili.com/"))
        self.driver.get(YJZ_CHANNEL)
        while True:
            try:
                WebDriverWait(self.driver, 10).until(
                    ec.presence_of_element_located((By.XPATH, '//div[@class="chat-history-panel"]')))
            except TimeoutError:
                Logger.err("login()", "Failed to load channel 528.")
                self.driver.get(YJZ_CHANNEL)
                continue
            else:
                break
        self.base_tab = self.driver.current_window_handle
        # WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, '//div[@id="sidebar-vm"]')))
        # self.delete_element(self.driver.find_element_by_xpath('//div[@id="sidebar-vm"]'))
        # WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, '//div[@id="my-dear-haruna-vm"]')))
        # self.delete_element(self.driver.find_element_by_xpath('//div[@id="my-dear-haruna-vm"]'))
        # WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, '//div[@id="live-player-ctnr"]')))
        # self.delete_element(self.driver.find_element_by_xpath('//div[@id="live-player-ctnr"]'))

    def to_loot_tab(self):
        self.driver.switch_to.window(self.loot_tab)

    def to_base_tab(self):
        self.driver.switch_to.window(self.base_tab)

    def clear_chat_history_panel(self):
        while True:
            try:
                self.driver.find_element_by_xpath('//span[@class="icon-item icon-font icon-clear"]').click()
            except ElementClickInterceptedException as _:
                try:
                    element = self.driver.find_element_by_xpath('//div[starts-with(@class, "function-bar")]')
                except NoSuchElementException:
                    Logger.err("clear_chat_history_panel()",
                               "Something obscures the clear screen button. Retry in 10 seconds.")
                    sleep(10)
                else:
                    try:
                        element.click()
                    except ElementClickInterceptedException as e:
                        Logger.err("clear_chat_history_panel()", "Unable to click 清楚弹幕. Retry.")
                        continue
            else:
                break

    def found_broadcast_msg(self) -> bool:
        """
        检查弹幕历史中是否有广播。如果有，加入到 waiting_list 中，并清除弹幕历史。如果没有则直接返回。
        :return:
        """
        latiaos = self.driver.find_elements_by_xpath('//div[@class="chat-item  system-msg border-box"]')
        if len(latiaos) == 0:
            return False
        for latiao in latiaos:
            try:
                link = latiao.find_element_by_tag_name('a').get_attribute('href')
            except NoSuchElementException as e:
                link = YJZ_CHANNEL
            if link not in self.set:
                self.waiting_list.append(link)
                print(link)
                self.set.add(link)
        self.clear_chat_history_panel()
        return True

    def load_tab(self, link):
        self.driver.execute_script(f"window.open('{link}')")
        WebDriverWait(self.driver, 10).until(ec.number_of_windows_to_be(2))
        tabs = self.driver.window_handles
        self.loot_tab = [tab for tab in tabs if tab != self.base_tab][0]
        self.driver.switch_to.window(self.loot_tab)
        _ = WebDriverWait(self.driver, 5).until(
            ec.presence_of_element_located((By.XPATH, '//div[starts-with(@class, "function-bar")]'))
        )

    def get_wait_time(self) -> int:
        element = self.driver.find_element_by_xpath('//div[starts-with(@class, "function-bar")]')
        if element.text == '点击领奖':
            return 0
        else:
            s = element.text.replace('等待开奖', '')
            try:
                second = int(s.split(":")[1]) + int(s.split(":")[0]) * 60
            except IndexError:
                return 0
            return second

    def get_caster_name(self) -> str:
        return self.driver.find_element_by_xpath('//a[starts-with(@class, "room-owner-username")]').text

    def close_tab(self):
        self.driver.execute_script("window.close()")
        WebDriverWait(self.driver, 10).until(ec.number_of_windows_to_be(1))
        self.driver.switch_to.window(self.base_tab)

    def collect(self):
        element = self.driver.find_element_by_xpath('//div[starts-with(@class, "function-bar")]')
        sender_info_text = str(self.driver.find_element_by_xpath('//div[@class="gift-sender-info"]').text)
        while True:
            try:
                element.click()
            except ElementClickInterceptedException as e:
                try:
                    shit = self.driver.find_element_by_xpath('//div[@class="draw-bingo-cntr draw-bingo-cntr"]')
                    self.delete_element(shit)
                except NoSuchElementException as ee:
                    Logger.err('collect', "", e)
                    Logger.err('collect', "", ee)
                    Logger.log(f'啥都没领到')
                    return
                continue
            except StaleElementReferenceException as e:
                Logger.err("collect()", "点击领奖 Staled", e)
                Logger.log(f'啥都没领到')
                return
            else:
                break
        loot = "辣条" if "赠送" in sender_info_text else \
            "辣条" if "赢得大乱斗PK胜利" in sender_info_text else \
                "亲密度" if "上任" in sender_info_text else "不知道什么东西"
        Logger.log(f'{sender_info_text} {loot}到手')

    def have_latiao(self) -> bool:
        try:
            self.driver.find_element_by_xpath('//div[starts-with(@class, "function-bar")]')
        except NoSuchElementException:
            return False
        return True

    def main(self):
        self.login()
        while True:
            if len(self.waiting_list) == 0:
                while not self.found_broadcast_msg():
                    sleep(5)
            for link in self.waiting_list:
                try:
                    print("Load tab C")
                    self.load_tab(link)
                except TimeoutException as e:
                    print("Timeout")
                    print("Close tab C")
                    self.close_tab()
                    continue
                caster_name = self.get_caster_name()
                waiting_time = self.get_wait_time()
                self.queue.put(Channel(link, caster_name, datetime.now() + timedelta(seconds=waiting_time)))
                print("Close tab C")
                self.close_tab()
            while not self.queue.empty():
                channel = self.queue.get()
                print(channel.caster, channel.link, channel.due_time)
                Logger.caster = channel.caster
                if len(self.driver.window_handles) == 2 and self.driver.current_url != channel.link.replace('http',
                                                                                                            'https'):
                    try:
                        self.close_tab()
                        self.load_tab(channel.link)
                    except TimeoutException as e:
                        print(e)
                        self.set.remove(channel.link)
                        continue
                print(self.driver.current_url, channel.link)
                try:
                    waiting_time = self.get_wait_time()
                except NoSuchElementException as e:
                    print(e)
                    self.set.remove(channel.link)
                    continue
                if waiting_time > 10:
                    print("too long", waiting_time)
                    if self.driver.current_url != YJZ_CHANNEL:
                        self.close_tab()
                    for i in range((waiting_time - 10) // 5):
                        self.found_broadcast_msg()
                        sleep(5)
                    if self.driver.current_url != YJZ_CHANNEL:
                        try:
                            print("Load tab B")
                            self.load_tab(channel.link)
                        except TimeoutException as e:
                            print(e)
                            self.set.remove(channel.link)
                            continue
                while self.have_latiao():
                    try:
                        waiting_time = self.get_wait_time()
                    except NoSuchElementException as e:
                        print(e)
                        self.set.remove(channel.link)
                        continue
                    if waiting_time < 10:
                        while self.get_wait_time() != 0:
                            pass
                        self.collect()
                    else:
                        break
                if self.have_latiao():
                    print("Add back", waiting_time)
                    self.queue.put(
                        Channel(channel.link, channel.caster, datetime.now() + timedelta(seconds=waiting_time)))
                else:
                    print("channel.link = " + channel.link)
                    self.set.remove(channel.link)


if __name__ == '__main__':
    LatiaoAid().main()
