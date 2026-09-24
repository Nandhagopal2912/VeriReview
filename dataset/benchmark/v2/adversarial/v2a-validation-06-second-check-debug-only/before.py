def transfer(source, target, amount):
    source.balance -= amount
    target.balance += amount
