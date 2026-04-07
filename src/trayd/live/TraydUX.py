from alpaca.trading.models import Position, Order
from alpaca.trading.enums import OrderSide

import dearpygui.dearpygui as dpg
from live.Portfolio import Portfolio
from live.Config import Config
from live.Logger import Logger
from live.models import LocalPosition

from live.helpers import format_USD

from collections import deque
from datetime import datetime

import platform
import time
import queue

class TraydUX:
    def __init__(self, portfolio: Portfolio):
        self.running = False
        self.render_rate = 1 / Config.ux_render_framerate
        self.since_last_render = 0.0
        self.since_last_draw = 0.0
        self.portfolio = portfolio
        self.log_queue = queue.Queue()  # queue object for logger
        self.event_queue = queue.Queue()  # queue object for logger

        # Store logger text
        self.logger_lines = []
        self.event_lines = []

        # Data for the line graph
        
        self.graph_points = deque()
        self.start_time = time.time()
        self.last_graph_update = self.start_time

        self.since_quit_clicked = 0

        self.wants_to_exit = False


    def restart(self, algorithm_name: str):
        self.stop()
        self.initialize(algorithm_name)

    def initialize(self, algorithm_name: str):
        dpg.create_context()
        with dpg.font_registry():
            default_font = dpg.add_font("C:/Windows/Fonts/arial.ttf", 20)  # 24 px size

        with dpg.theme(tag="red_button_theme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 50, 50, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (220, 70, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (180, 40, 40, 255))

        with dpg.theme(tag="green_button_theme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 180, 90, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 200, 110, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 160, 80, 255))

        with dpg.theme(tag="thick_line_theme"):
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 10.0)


        dpg.bind_font(default_font)
        dpg.create_viewport(title="TraydLlama", width=1430, height=800, resizable=False)
        dpg.set_viewport_clear_color((30, 30, 60, 255))
        dpg.setup_dearpygui()
        dpg.show_viewport()

        with dpg.window(label="Portfolio Dashboard", width=1420, height=800, no_move=True, no_close=True, no_collapse=True, no_resize=True):

            # Horizontal group for columns
            with dpg.group(horizontal=True):

                # Portfolio info (left column)
                with dpg.group(horizontal=False, width=175):
                    dpg.add_text(f"{algorithm_name}")
                    dpg.add_text(f"BUYP: N/A", tag="bp_text")
                    # dpg.add_text(f"ALLOWANCE: N/A", tag="allowance_text")
                    dpg.add_text(f"TOTAL: N/A", tag="portfolio_value_text")
                    # dpg.add_text(f"HELD: N/A", tag="holdings_value_text")
                    dpg.add_text(f"NOT CONNECTED", tag="connection_text")
                    dpg.add_text(f"NORMAL HOURS", tag="hours_text")


                    with dpg.child_window(width=-1, height=170, autosize_y=False, border=False):
                        # dpg.add_button(label="BUY", callback=self.on_buy_click, width=100, height=40)
                        # self.update_buy_color(dpg.last_item())

                        # dpg.add_button(label="SELL", callback=self.on_sell_click, width=100, height=40)
                        # self.update_sell_color(dpg.last_item())

                        dpg.add_spacer(height=10)

                        dpg.add_button(label="RUN", callback=self.on_run_click, width=135, height=50, indent=20)
                        self.update_run_color(dpg.last_item())

                        dpg.add_spacer(height=10)

                        dpg.add_button(label="EXIT", callback=self.on_exit_click, width=135, height=50, indent=20)
                        
                        self.update_exit_color(dpg.last_item())

                # # Stats
                # with dpg.child_window(width=200, height=300, autosize_y=False, horizontal_scrollbar=True):
                #     dpg.add_text("Day Stats", tag="stats_title")
                #     dpg.add_text("", tag="stats_text")


                # Positions (middle column, scrollable)
                with dpg.child_window(width=400, height=300, autosize_y=False, horizontal_scrollbar=True):
                    dpg.add_text("Positions", tag="positions_title")
                    dpg.add_text("", tag="positions_text")

                # Orders (left column, scrollable)
                with dpg.child_window(width=400, height=300, autosize_y=False, horizontal_scrollbar=True):
                    dpg.add_text("Orders", tag="orders_title")
                    dpg.add_text("", tag="orders_text")

                # Events (middle column, scrollable)
                with dpg.child_window(width=400, height=300, autosize_y=False, horizontal_scrollbar=True):
                    dpg.add_text("Events", tag="events_title")
                    dpg.add_text("", tag="events_text")

            with dpg.group(horizontal=True):
                # Ranks
                with dpg.child_window(width=170, height=400, autosize_y=False, horizontal_scrollbar=True):
                    dpg.add_text("Day Stats", tag="stats_title")
                    dpg.add_text("Slippage:", tag="slippage_text")
                    dpg.add_text("Profit:", tag="profit_text")


                # Line graph below portfolio and positions
                with dpg.plot(label="Portfolio Value Over Time", height=400, width=815):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", no_highlight=True)
                    self.x_axis = dpg.last_item()
                    self.y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Value", no_highlight=True)
                    self.line_series = dpg.add_line_series([], [], label="Portfolio Value", parent=self.y_axis)
                    
                    dpg.bind_item_theme(self.line_series, "thick_line_theme")

                # Logger (right column, scrollable)
                with dpg.child_window(width=400, height=400, autosize_y=False, horizontal_scrollbar=True):
                    dpg.add_text("Logger", tag="logger_title")
                    dpg.add_text("", tag="logger_text")

        self.running = True


    def update(self):
        if not self.running:
            return

        if not dpg.is_dearpygui_running():
            self.running = False
            return
        
        self.draw()
        self.render()


    def draw(self):
        if time.time() - Config.ux_draw_rate > self.since_last_draw:
            self.since_last_draw = time.time()
        else: return

        self.draw_frame()


    def render(self):
        if time.time() - self.render_rate > self.since_last_render:
            self.since_last_render = time.time()
        else: return

        dpg.render_dearpygui_frame()


    def draw_frame(self):
        self.draw_portfolio_info()
        self.draw_positions()
        self.draw_orders()
        self.draw_logger()
        self.draw_event_log()
        self.draw_line_graph()


    def draw_portfolio_info(self):
        dpg.set_value("bp_text", f"BUYP: {format_USD(self.portfolio.buying_power)}")
        # dpg.set_value("allowance_text", f"ALLOW: {format_USD(self.portfolio.allowance)}")
        dpg.set_value("portfolio_value_text", f"TOTAL: {format_USD(self.portfolio.portfolio_value)}")
        dpg.set_value("slippage_text", f"Slippage: {format_USD(self.portfolio.total_slippage)}")
        dpg.set_value("profit_text", f"Profits: {format_USD(self.portfolio.profit)}")
        # dpg.set_value("holdings_value_text", f"HELD: {format_USD(self.portfolio.holdings_value)}")


    def draw_positions(self):
        if self.portfolio.positions:
            positions_lines = []
            for symbol, info in self.portfolio.positions.items():
                info: LocalPosition
                shares = int(info.qty)
                price = format_USD(shares * float(info.avg_entry_price))
                positions_lines.append(f"{symbol}: {shares} share(s) at {price}")
            positions_text = "\n".join(positions_lines)
        else:
            positions_text = ""
        dpg.set_value("positions_text", positions_text)


    def draw_orders(self):
        # Update Orders
        if self.portfolio.orders:
            order_lines = []
            for order in self.portfolio.orders.values():
                order: Order
                shares = int(order.qty)
                price = "market $"
                if order.limit_price:
                    price = format_USD(shares * float(order.limit_price))
                prefix = "BUY" if order.side == OrderSide.BUY else "SELL"
                order_lines.append(f"{prefix} {order.symbol}: {shares} share(s) at {price}")
            orders_text = "\n".join(order_lines)
        else:
            orders_text = ""
        dpg.set_value("orders_text", orders_text)


    def draw_logger(self):
        # Update logger from queue
        while not self.log_queue.empty():
            log_msg = self.log_queue.get()
            self.logger_lines.append(log_msg)

        # Keep last 100 logs
        if len(self.logger_lines) > 16:
            self.logger_lines = self.logger_lines[-16:]
        dpg.set_value("logger_text", "\n".join(self.logger_lines))


    def draw_event_log(self):
        # Update events from queue
        while not self.event_queue.empty():
            event_msg = self.event_queue.get()
            self.event_lines.append(event_msg)

        # Keep last 100 logs
        if len(self.event_lines) > 12:
            self.event_lines = self.event_lines[-12:]
        dpg.set_value("events_text", "\n".join(self.event_lines))


    def draw_line_graph(self):
        current_time = time.time()
        elapsed = current_time - self.start_time

        # Initialize graph_points deque if not exists
        if not hasattr(self, "graph_points"):
            self.graph_points = deque()

        # Append new point
        self.graph_points.append((elapsed, self.portfolio.portfolio_value))

        # Keep only last 180 seconds
        cutoff = elapsed - 180
        while self.graph_points and self.graph_points[0][0] < cutoff:
            self.graph_points.popleft()

        if not self.graph_points:
            return

        # Prepare points as list of (x, y) tuples
        margin_seconds = 10
        display_points = [(t - cutoff, v) for t, v in self.graph_points]

        # Update line series with points
        display_x = [float(t - cutoff) for t, v in self.graph_points]
        display_y = [float(v) for t, v in self.graph_points]

        # Update line series: must be two lists, not a list of tuples
        dpg.set_value(self.line_series, [display_x, display_y])

        # Set X-axis limits
        dpg.set_axis_limits(self.x_axis, 0, 180 + margin_seconds)

        # Set Y-axis limits around current value
        current_value = self.portfolio.portfolio_value
        margin_percent = 0.005
        dpg.set_axis_limits(
            self.y_axis,
            current_value * (1 - margin_percent),
            current_value * (1 + margin_percent)
        )

    def set_connected(self, connected: bool):
        if connected:
            dpg.set_value("connection_text", "CONNECTED")
        else:
            dpg.set_value("connection_text", "NOT CONNECTED")

    def set_extended(self, extended: bool):
        if extended:
            dpg.set_value("hours_text", "EXTENDED HOURS")
        else:
            dpg.set_value("hours_text", "REGULAR HOURS")


    def log_message(self, msg: str):
        self.log_queue.put(msg)

    def log_event(self, msg: str):
        self.event_queue.put(msg)


    def on_buy_click(self, sender):
        Config.can_buy = not Config.can_buy

        if Config.can_buy:
            Logger.log_message("Buying enabled")
        else:
            Logger.log_message("Buying disabled")

        self.update_buy_color(sender)

    def update_buy_color(self, buy_button):
        if Config.can_buy:
            dpg.bind_item_theme(buy_button, "green_button_theme")
        else:
            dpg.bind_item_theme(buy_button, "red_button_theme")

    def on_sell_click(self, sender):
        Config.can_sell = not Config.can_sell

        if Config.can_sell:
            Logger.log_message("Selling enabled")
        else:
            Logger.log_message("Selling disabled")

        self.update_sell_color(sender)

    def update_sell_color(self, sell_button):
        if Config.can_sell:
            dpg.bind_item_theme(sell_button, "green_button_theme")
        else:
            dpg.bind_item_theme(sell_button, "red_button_theme")

    def on_run_click(self, sender):
        Config.can_run = not Config.can_run

        if Config.can_run:
            Logger.log_message("Algorithm enabled")
        else:
            Logger.log_message("Algorithm disabled")

        self.update_run_color(sender)

    def update_run_color(self, run_button):
        if Config.can_run:
            dpg.bind_item_theme(run_button, "green_button_theme")
        else:
            dpg.bind_item_theme(run_button, "red_button_theme")
    
    def on_exit_click(self, sender):
        if time.time() - self.since_quit_clicked < 0.5:
            self.wants_to_exit = True
        else:
            self.since_quit_clicked = time.time()
            Logger.log_message("Click twice to exit")

    def update_exit_color(self, quit_button):
        dpg.bind_item_theme(quit_button, "red_button_theme")


    def add_trade(self, trade):
        pass

    def stop(self):
        dpg.destroy_context()

    def is_running(self):
        if self.running:
            return dpg.is_dearpygui_running()
