
total = 0

for i in range(2, 101, 2):          # 取 2~100 的偶數
    if '3' not in str(i):            # 如果數字 i 裡面沒有「3」
        total += i                   # 才把 i 加進總和

print(total)