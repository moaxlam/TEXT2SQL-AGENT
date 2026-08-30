-- Sample data for the e-commerce database

INSERT INTO customers (customer_id, name, email, city, country) VALUES
(1, 'Alice Johnson', 'alice@example.com', 'New York', 'US'),
(2, 'Bob Smith', 'bob@example.com', 'London', 'UK'),
(3, 'Carol White', 'carol@example.com', 'Paris', 'FR'),
(4, 'David Brown', 'david@example.com', 'Tokyo', 'JP'),
(5, 'Eva Martinez', 'eva@example.com', 'Madrid', 'ES');

INSERT INTO products (product_id, name, category, price, stock_quantity) VALUES
(1, 'Laptop Pro 15', 'Electronics', 1299.99, 50),
(2, 'Wireless Mouse', 'Electronics', 29.99, 200),
(3, 'Python Cookbook', 'Books', 45.99, 100),
(4, 'Standing Desk', 'Furniture', 599.99, 30),
(5, 'Noise Cancelling Headphones', 'Electronics', 199.99, 75),
(6, 'Mechanical Keyboard', 'Electronics', 89.99, 120),
(7, 'Data Science Handbook', 'Books', 39.99, 80),
(8, 'Ergonomic Chair', 'Furniture', 449.99, 25);

INSERT INTO orders (order_id, customer_id, order_date, status, total_amount) VALUES
(1, 1, '2026-01-15', 'delivered', 1329.98),
(2, 2, '2026-02-20', 'delivered', 245.98),
(3, 1, '2026-03-10', 'shipped', 89.99),
(4, 3, '2026-04-05', 'pending', 1049.98),
(5, 4, '2026-05-12', 'delivered', 599.99),
(6, 5, '2026-06-01', 'shipped', 289.98),
(7, 2, '2026-07-15', 'pending', 449.99);

INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 1, 1299.99),
(2, 1, 2, 1, 29.99),
(3, 2, 3, 2, 45.99),
(4, 2, 5, 1, 199.99),
(5, 3, 6, 1, 89.99),
(6, 4, 4, 1, 599.99),
(7, 4, 5, 1, 199.99),
(8, 4, 2, 2, 29.99),
(9, 5, 4, 1, 599.99),
(10, 6, 5, 1, 199.99),
(11, 6, 7, 1, 39.99),
(12, 6, 2, 1, 29.99),
(13, 7, 8, 1, 449.99);

INSERT INTO reviews (review_id, product_id, customer_id, rating, comment) VALUES
(1, 1, 1, 5, 'Excellent laptop, fast and reliable'),
(2, 2, 1, 4, 'Good mouse, comfortable to use'),
(3, 3, 2, 5, 'Great cookbook for Python developers'),
(4, 5, 2, 4, 'Good noise cancellation'),
(5, 6, 1, 5, 'Best keyboard I have ever used'),
(6, 4, 3, 3, 'Decent desk but assembly was tricky'),
(7, 7, 5, 4, 'Comprehensive data science reference'),
(8, 8, 2, 5, 'Very comfortable for long work sessions');
