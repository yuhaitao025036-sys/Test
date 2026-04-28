import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import matplotlib.pyplot as plt

# ============================================================
# 第 1 部分：生成数据
# ============================================================

def generate_data(num_samples=200):
    """
    生成训练数据：y = 2*x1 + 3*x2 + 1 + 噪声
    """
    torch.manual_seed(42)
    
    # 生成输入数据（2 个特征）
    X = torch.randn(num_samples, 2) * 2
    
    # 生成目标数据（线性关系 + 噪声）
    y = 2 * X[:, 0] + 3 * X[:, 1] + 1 + torch.randn(num_samples) * 0.1
    
    # 调整形状
    y = y.unsqueeze(1)  # (num_samples, 1)
    
    return X, y

# ============================================================
# 第 2 部分：定义模型
# ============================================================

class SimpleNeuralNetwork(nn.Module):
    """简单的神经网络"""
    
    def __init__(self, input_size=2, hidden_size=16):
        super(SimpleNeuralNetwork, self).__init__()
        
        # 第 1 层：输入层 → 隐层
        self.fc1 = nn.Linear(input_size, hidden_size)
        
        # 激活函数
        self.relu = nn.ReLU()
        
        # 第 2 层：隐层 → 输出层
        self.fc2 = nn.Linear(hidden_size, 1)
    
    def forward(self, x):
        # 前向传播
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

# ============================================================
# 第 3 部分：定义训练函数
# ============================================================

def train(
    model,
    train_loader,
    num_epochs=50,
    learning_rate=0.01,
    optimizer_name='SGD',
    print_every=10
):
    """
    训练模型
    
    参数：
        model: 神经网络模型
        train_loader: 数据加载器
        num_epochs: 训练轮数
        learning_rate: 学习率
        optimizer_name: 优化器名称（'SGD' 或 'Adam'）
        print_every: 每隔多少轮打印一次
    """
    
    # 定义损失函数
    criterion = nn.MSELoss()  # 均方误差
    
    # 选择优化器
    if optimizer_name == 'SGD':
        optimizer = optim.SGD(model.parameters(), lr=learning_rate)
    elif optimizer_name == 'Adam':
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_name}")
    
    # 记录训练过程
    loss_history = []
    
    print(f"\n{'='*60}")
    print(f"训练配置：")
    print(f"  优化器: {optimizer_name}")
    print(f"  学习率: {learning_rate}")
    print(f"  迭代次数: {num_epochs}")
    print(f"{'='*60}\n")
    
    # 训练循环
    for epoch in range(num_epochs):
        epoch_loss = 0
        batch_count = 0
        
        # 遍历所有批次
        for batch_idx, (X_batch, y_batch) in enumerate(train_loader):
            
            # 第 1 步：清零梯度
            optimizer.zero_grad()
            
            # 第 2 步：前向传播
            y_pred = model(X_batch)
            
            # 第 3 步：计算损失
            loss = criterion(y_pred, y_batch)
            
            # 第 4 步：反向传播
            loss.backward()
            
            # 第 5 步：更新参数
            optimizer.step()
            
            # 记录损失
            epoch_loss += loss.item()
            batch_count += 1
        
        # 计算平均损失
        avg_loss = epoch_loss / batch_count
        loss_history.append(avg_loss)
        
        # 打印日志
        if (epoch + 1) % print_every == 0:
            print(f"Epoch [{epoch+1:3d}/{num_epochs}] | Loss: {avg_loss:.6f}")
    
    print(f"\n{'='*60}")
    print(f"训练完成！最终 Loss: {avg_loss:.6f}")
    print(f"{'='*60}\n")
    
    return loss_history

# ============================================================
# 第 4 部分：定义评估函数
# ============================================================

def evaluate(model, X_test, y_test):
    """
    在测试集上评估模型
    """
    model.eval()  # 切换到评估模式
    
    with torch.no_grad():  # 不计算梯度
        y_pred = model(X_test)
        loss = nn.MSELoss()(y_pred, y_test)
    
    return loss.item(), y_pred

# ============================================================
# 第 5 部分：可视化
# ============================================================

def plot_results(loss_history, y_true, y_pred):
    """
    绘制训练过程和预测结果
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    
    # 左图：训练 Loss 变化
    axes[0].plot(loss_history, 'b-', linewidth=2)
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Training Loss Over Time')
    axes[0].grid(True, alpha=0.3)
    
    # 右图：真实 vs 预测
    axes[1].scatter(y_true.numpy(), y_pred.numpy(), alpha=0.6, s=20)
    
    # 画对角线（完美预测）
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    axes[1].plot([min_val, max_val], [min_val, max_val], 'r--', 
                 label='Perfect Prediction', linewidth=2)
    
    axes[1].set_xlabel('True Values')
    axes[1].set_ylabel('Predicted Values')
    axes[1].set_title('True vs Predicted')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('training_results.png', dpi=100)
    print("图已保存为 training_results.png")
    plt.show()

# ============================================================
# 第 6 部分：主程序
# ============================================================

if __name__ == "__main__":
    
    # ========== 参数配置（可以调整这些）==========
    NUM_SAMPLES = 300
    BATCH_SIZE = 16
    NUM_EPOCHS = 500          # ← 可调：迭代次数
    LEARNING_RATE = 0.03      # ← 可调：学习率
    OPTIMIZER = 'SGD'        # ← 可调：优化器 ('SGD' 或 'Adam')
    HIDDEN_SIZE = 16
    # ==========================================
    
    print("生成数据...")
    X, y = generate_data(NUM_SAMPLES)
    
    # 分割训练集和测试集
    split_idx = int(0.8 * NUM_SAMPLES)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"训练集大小: {X_train.shape[0]}")
    print(f"测试集大小: {X_test.shape[0]}")
    
    # 创建数据加载器
    dataset = TensorDataset(X_train, y_train)
    train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    # 创建模型
    print("\n创建模型...")
    model = SimpleNeuralNetwork(input_size=2, hidden_size=HIDDEN_SIZE)
    print(model)
    
    # 统计参数数量
    num_params = sum(p.numel() for p in model.parameters())
    print(f"模型参数数量: {num_params}")
    
    # 训练模型
    print("\n开始训练...")
    loss_history = train(
        model,
        train_loader,
        num_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        optimizer_name=OPTIMIZER,
        print_every=max(1, NUM_EPOCHS // 10)  # 均匀打印
    )
    
    # 在测试集上评估
    print("在测试集上评估...")
    test_loss, y_pred = evaluate(model, X_test, y_test)
    print(f"测试集 Loss: {test_loss:.6f}")
    
    # 可视化结果
    print("\n绘制结果...")
    plot_results(loss_history, y_test, y_pred)
    
    # 打印一些预测示例
    print("\n预测示例：")
    print(f"{'输入':>20} {'真实值':>15} {'预测值':>15} {'误差':>15}")
    print("-" * 65)
    
    for i in range(min(5, len(X_test))):
        x = X_test[i]
        true_y = y_test[i].item()
        pred_y = y_pred[i].item()
        error = abs(true_y - pred_y)
        
        print(f"{str(x.tolist()):>20} {true_y:>15.6f} {pred_y:>15.6f} {error:>15.6f}")