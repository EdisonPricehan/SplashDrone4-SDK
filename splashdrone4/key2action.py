import sys
from pynput import keyboard
from typing import Optional, List
import random
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


class Key2Action:
    def __init__(self):
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        self.last_key = None

    def on_press(self, key):
        try:
            pass
            # print('alphanumeric key {0} pressed'.format(key.char))
        except AttributeError:
            log.error('special key {0} pressed'.format(key))

    def on_release(self, key):
        # print('{0} released'.format(key))
        if key == keyboard.Key.esc:
            return  # Stop listener

        try:
            self.last_key = key.char
            log.debug(f'Key pressed: {self.last_key}')
        except AttributeError:
            if key in [keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down]:
                self.last_key = str(key)  # e.g., 'Key.left'
                # print(f'{self.last_key=}')
            elif key == keyboard.Key.space:
                self.last_key = 'space'
            else:
                self.last_key = None

    def get_arrow_key(self) -> Optional[str]:
        if self.last_key is None:
            return None

        arrow = None
        if self.last_key == 'Key.up':
            arrow = 'up'
        elif self.last_key == 'Key.down':
            arrow = 'down'
        elif self.last_key == 'Key.left':
            arrow = 'left'
        elif self.last_key == 'Key.right':
            arrow = 'right'
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting arrow key')

        if arrow is not None:
            self.last_key = None

        return arrow

    def get_space_key(self) -> Optional[str]:
        if self.last_key is None:
            return None

        if self.last_key == 'space':
            self.last_key = None
            return 'space'
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting space key')
            return None

    def get_reset_action(self) -> Optional[str]:
        if self.last_key is None:
            return None

        if self.last_key == 'r':
            self.last_key = None
            return 'reset'
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting reset key')
            return None

    def get_good_to_go_key(self) -> Optional[str]:
        if self.last_key is None:
            return None

        if self.last_key == 'g':
            self.last_key = None
            return 'good_to_go'
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting good-to-go key')
            return None

    def get_multi_discrete_action(self) -> Optional[List[int]]:
        if self.last_key is None:
            return None

        action = [1] * 4  # [up-down, yaw, forward-backward, left-right]
        if self.last_key == 'w':
            action[0] = 0
        elif self.last_key == 's':
            action[0] = 2
        elif self.last_key == 'a':
            action[1] = 0
        elif self.last_key == 'd':
            action[1] = 2
        elif self.last_key == 'i':
            action[2] = 0
        elif self.last_key == 'k':
            action[2] = 2
        elif self.last_key == 'j':
            action[3] = 0
        elif self.last_key == 'l':
            action[3] = 2
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting multi-discrete action')
            action = None

        if action is not None:
            self.last_key = None

        return action

    def get_discrete_action(self) -> Optional[int]:
        if self.last_key is None:
            return None

        action = None
        if self.last_key == 'w':
            action = 1
        elif self.last_key == 's':
            action = 2
        elif self.last_key == 'a':
            action = 3
        elif self.last_key == 'd':
            action = 4
        elif self.last_key == 'i':
            action = 5
        elif self.last_key == 'k':
            action = 6
        elif self.last_key == 'j':
            action = 7
        elif self.last_key == 'l':
            action = 8
        else:
            log.debug(f'Unrecognized key {self.last_key} when getting discrete action')

        if action is not None:
            self.last_key = None

        return action

    def get_random_action(self, multi_discrete: bool = False):
        if multi_discrete:  # one-hot
            action = [1] * 4
            axis = random.randint(0, 3)
            direction = random.randint(0, 2)
            action[axis] = direction
            return action
        else:
            return [random.randint(0, 8)]

    def stop(self):
        self.listener.stop()


if __name__ == '__main__':
    # ...or, in a non-blocking fashion:
    # listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    # listener.start()

    # Collect events until released
    # with keyboard.Listener(
    #         on_press=on_press,
    #         on_release=on_release) as listener:
    #     listener.join()

    import time
    k2a = Key2Action()
    try:
        while True:
            arrow_key = k2a.get_arrow_key()
            if arrow_key is not None:
                print(f'Arrow key pressed: {arrow_key}')

            space_key = k2a.get_space_key()
            if space_key == 'space':
                print(f'Space key pressed.')

            reset_key = k2a.get_reset_action()
            if reset_key == 'reset':
                print(f'Reset key pressed.')

            action = k2a.get_multi_discrete_action()
            if action is not None:
                print(f'Action pressed: {action}')

            time.sleep(0.1)
    except KeyboardInterrupt:
        k2a.stop()


