from browser import document, html, timer

CELL_SIZE = 40
WALL_THICKNESS = 6
IMG_PATH = "https://mde.tw/cp2025/reeborg/src/images/"

class World:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.layers = self._create_layers()
        self._init_html()
        self._draw_grid()
        self._draw_walls()
        
    def _create_layers(self):
        return {
            "grid": html.CANVAS(width=self.width * CELL_SIZE, height=self.height * CELL_SIZE),
            "walls": html.CANVAS(width=self.width * CELL_SIZE, height=self.height * CELL_SIZE),
            "objects": html.CANVAS(width=self.width * CELL_SIZE, height=self.height * CELL_SIZE),
            "robots": html.CANVAS(width=self.width * CELL_SIZE, height=self.height * CELL_SIZE),
        }

    def _init_html(self):
        container = html.DIV(style={
            "position": "relative",
            "width": f"{self.width * CELL_SIZE}px",
            "height": f"{self.height * CELL_SIZE}px"
        })
        for z, canvas in enumerate(self.layers.values()):
            canvas.style = {
                "position": "absolute",
                "top": "0px",
                "left": "0px",
                "zIndex": str(z)
            }
            container <= canvas
        document["brython_div1"].clear()
        document["brython_div1"] <= container
        
    def _draw_grid(self):
        ctx = self.layers["grid"].getContext("2d")
        ctx.strokeStyle = "#cccccc"
        for i in range(self.width + 1):
            ctx.beginPath()
            ctx.moveTo(i * CELL_SIZE, 0)
            ctx.lineTo(i * CELL_SIZE, self.height * CELL_SIZE)
            ctx.stroke()
        for j in range(self.height + 1):
            ctx.beginPath()
            ctx.moveTo(0, j * CELL_SIZE)
            ctx.lineTo(self.width * CELL_SIZE, j * CELL_SIZE)
            ctx.stroke()

    def _draw_image(self, ctx, src, x, y, w, h, offset_x=0, offset_y=0):
        img = html.IMG()
        img.src = src
        def onload(evt):
            px = x * CELL_SIZE + offset_x
            # Bython/Reeborg world uses (1, 1) bottom-left, Canvas uses (0, 0) top-left
            # We convert the y-coordinate for drawing: (self.height - 1 - y)
            py = (self.height - 1 - y) * CELL_SIZE + offset_y
            ctx.drawImage(img, px, py, w, h)
        img.bind("load", onload)
        
    def _draw_walls(self):
        ctx = self.layers["walls"].getContext("2d")
        # 繪製上下邊界牆 (北牆和南牆)
        for x in range(self.width):
            # 北牆 (世界最上方一排格子的上緣)
            self._draw_image(ctx, IMG_PATH + "north.png", x, self.height - 1,
                             CELL_SIZE, WALL_THICKNESS, offset_y=0)
            # 南牆 (世界最下方一排格子的下緣)
            self._draw_image(ctx, IMG_PATH + "north.png", x, 0,
                             CELL_SIZE, WALL_THICKNESS, offset_y=CELL_SIZE - WALL_THICKNESS)
        # 繪製左右邊界牆 (西牆和東牆)
        for y in range(self.height):
            # 西牆 (世界最左方一排格子的左緣)
            self._draw_image(ctx, IMG_PATH + "east.png", 0, y,
                             WALL_THICKNESS, CELL_SIZE, offset_x=0)
            # 東牆 (世界最右方一排格子的右緣)
            self._draw_image(ctx, IMG_PATH + "east.png", self.width - 1, y,
                             WALL_THICKNESS, CELL_SIZE, offset_x=CELL_SIZE - WALL_THICKNESS)

    # 為了兼容舊版代碼保留的簡易 robot 繪製方法
    def robot(self, x, y):
        ctx = self.layers["robots"].getContext("2d")
        self._draw_image(ctx, IMG_PATH + "blue_robot_e.png", x - 1, y - 1,
                         CELL_SIZE, CELL_SIZE)

class AnimatedRobot:
    def __init__(self, world, x, y):
        self.world = world
        # 儲存機器人位置，使用 0-based 索引 (0, 0) 到 (width-1, height-1)
        self.x = x - 1
        self.y = y - 1
        self.facing = "E" # E: East, N: North, W: West, S: South
        self.facing_order = ["E", "N", "W", "S"]
        self.robot_ctx = world.layers["robots"].getContext("2d")
        self.trace_ctx = world.layers["objects"].getContext("2d")
        self.queue = [] # 儲存等待執行的動作
        self.running = False
        self._draw_robot()

    def _robot_image(self):
        # 根據方向回傳對應的圖片檔名
        return {
            "E": "blue_robot_e.png",
            "N": "blue_robot_n.png",
            "W": "blue_robot_w.png",
            "S": "blue_robot_s.png"
        }[self.facing]

    def _draw_robot(self):
        # 清除舊的機器人，然後在新的位置繪製
        self.robot_ctx.clearRect(0, 0, self.world.width * CELL_SIZE, self.world.height * CELL_SIZE)
        self.world._draw_image(self.robot_ctx, IMG_PATH + self._robot_image(),
                               self.x, self.y, CELL_SIZE, CELL_SIZE)

    def _draw_trace(self, from_x, from_y, to_x, to_y):
        # 繪製移動軌跡線
        ctx = self.trace_ctx
        ctx.strokeStyle = "#d33"
        ctx.lineWidth = 2
        ctx.beginPath()
        
        # 轉換為 Canvas 坐標系並找到格子中心點
        fx = from_x * CELL_SIZE + CELL_SIZE / 2
        fy = (self.world.height - 1 - from_y) * CELL_SIZE + CELL_SIZE / 2
        tx = to_x * CELL_SIZE + CELL_SIZE / 2
        ty = (self.world.height - 1 - to_y) * CELL_SIZE + CELL_SIZE / 2
        
        ctx.moveTo(fx, fy)
        ctx.lineTo(tx, ty)
        ctx.stroke()

    def move(self, steps):
        # 將移動動作加入佇列
        def action(next_done):
            def step():
                nonlocal steps
                if steps == 0:
                    next_done() # 移動完成，執行下一個動作
                    return
                
                from_x, from_y = self.x, self.y
                dx, dy = 0, 0
                
                # 根據目前方向確定移動向量
                if self.facing == "E": dx = 1
                elif self.facing == "W": dx = -1
                elif self.facing == "N": dy = 1
                elif self.facing == "S": dy = -1
                    
                next_x = self.x + dx
                next_y = self.y + dy
            
                # 檢查是否撞到邊界
                if 0 <= next_x < self.world.width and 0 <= next_y < self.world.height:
                    self.x, self.y = next_x, next_y
                    self._draw_trace(from_x, from_y, self.x, self.y)
                    self._draw_robot()
                    steps -= 1
                    timer.set_timeout(step, 200) # 延遲 200 毫秒進行下一步
                else:
                    print(f"🚨 嘗試從 ({from_x+1}, {from_y+1}) 往 {self.facing} 移動時撞牆，停止移動！")
                    next_done() # 撞牆，中止動作並執行下一個動作
                    
            step()
        self.queue.append(action)
        self._run_queue()

    def turn_left(self):
        # 將左轉動作加入佇列
        def action(done):
            idx = self.facing_order.index(self.facing)
            self.facing = self.facing_order[(idx + 1) % 4] # 往左轉 90 度
            self._draw_robot()
            timer.set_timeout(done, 300) # 延遲 300 毫秒，讓轉彎動畫完成
        self.queue.append(action)
        self._run_queue()

    def _run_queue(self):
        # 執行佇列中的下一個動作
        if self.running or not self.queue:
            return
        self.running = True
        action = self.queue.pop(0)
        action(lambda: self._done())

    def _done(self):
        # 目前動作執行完畢，準備執行佇列中的下一個動作
        self.running = False
        self._run_queue()


# --- 程式主體：定義世界和機器人動作 ---
w = World(10, 10)    # 建立 10x10 的世界 (格子範圍是 x=1到10, y=1到10)

# 在 (1, 1) 放置一台機器人 (這是 1-based 坐標)
r = AnimatedRobot(w, 1, 1)

# --- 爬階梯函式 (Stair Climbing Function) ---
def step_up():
    """執行一個完整的階梯動作：向右 (E) 1 步，向上 (N) 1 步，然後轉回東方。"""
    
    # 1. 向右 (E) 走 1 步
    r.move(1)
    
    # 2. 轉向北方 (N)
    r.turn_left()
    
    # 3. 向上 (N) 走 1 步
    r.move(1)
    
    # 4. 連續左轉 3 次，將方向從 N 轉回 E (N -> W -> S -> E)
    # 這樣下一次呼叫 move(1) 時，它就會再次向右走
    r.turn_left()
    r.turn_left()
    r.turn_left()

# 機器人從 (1, 1) 開始，要爬到最高點需要 9 個完整的階梯動作
# 每個 step_up() 會讓 X 坐標和 Y 坐標都增加 1
# 9 次之後，機器人會到達 (1+9, 1+9) = (10, 10)
for i in range(9):
    step_up()