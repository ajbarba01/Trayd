from tqdm import tqdm
import threading


class ProgressBar:
    def __init__(
        self,
        description: str = "Processing",
        leave: bool = False,
        show_unit: bool = True,
    ):
        self.item_idxs = {}
        self.items = []
        self.total = 0
        self.current_index = 0
        self.current_unit = ""
        self.current_tick = 0
        self.description = description
        self.leave = leave
        self.show_unit = show_unit
        self._pbar = None
        self._lock = threading.Lock()

        self.coarse = False
        self.coarse_ticks = 0

    def start(self, units: list[str], num_ticks: int = None):
        if not units:
            return

        self.coarse = num_ticks is not None
        if self.coarse:
            self.coarse_ticks = num_ticks

        self.units = units
        self.total = len(units)
        self.current_unit = units[self.current_index]
        self._set_item_idxs()
        self._pbar = tqdm(
            total=self.total,
            desc=self._get_description(),
            unit="unit",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]",
            colour="white",
            leave=self.leave,
        )

    def _get_description(self):
        return (
            f"{self.description}: {self.current_unit}"
            if self.show_unit
            else f"{self.description}"
        )

    def _set_item_idxs(self):
        self.item_idxs = {item: i for i, item in enumerate(self.items)}

    def set_item(self, item: str):
        with self._lock:
            self._set_current_index(self.items[item])

    def next(self):
        with self._lock:
            if self.current_index >= self.total:
                self.stop()
                return  # Already finished

            self.current_index += 1
            if self.coarse:
                self._set_coarse_tick()

            else:
                self._set_current_index(self.current_index)

    def _set_coarse_tick(self):
        tick = int(self.current_index / self.total * self.coarse_ticks)
        if self.current_tick != tick:
            self.current_tick = tick
            self._set_current_index(self.current_index)

    def stop(self):
        if self._pbar is not None:
            self._pbar.close()
            self._pbar = None

    def _set_current_index(self, idx: int):
        if idx >= self.total:
            return

        self.current_index = idx

        self.current_unit = self.units[self.current_index]
        self._set_progress(idx)

    def _set_progress(self, idx: int):
        self._pbar.set_description(self._get_description())

        self._pbar.n = min(idx + 1, self.total)
        self._pbar.refresh()
