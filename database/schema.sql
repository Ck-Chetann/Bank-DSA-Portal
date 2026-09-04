USE bank_dsa_portal;

-- 1. Users
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(15),
    password VARCHAR(255) NOT NULL,
    role ENUM('ADMIN', 'DSA', 'BANK_EMPLOYEE') NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. DSA Profiles
CREATE TABLE dsa_profiles (
    dsa_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    profile_description TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    address VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- 3. Bank Employees
CREATE TABLE bank_employees (
    employee_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    bank_name VARCHAR(150) NOT NULL,
    branch VARCHAR(150),
    city VARCHAR(100),
    state VARCHAR(100),
    official_email VARCHAR(150),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- 4. Loan Types
CREATE TABLE loan_types (
    loan_id INT AUTO_INCREMENT PRIMARY KEY,
    loan_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- 5. DSA Loans
CREATE TABLE dsa_loans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dsa_id INT NOT NULL,
    loan_id INT NOT NULL,
    FOREIGN KEY (dsa_id) REFERENCES dsa_profiles(dsa_id)
        ON DELETE CASCADE,
    FOREIGN KEY (loan_id) REFERENCES loan_types(loan_id)
        ON DELETE CASCADE,
    UNIQUE (dsa_id, loan_id)
);

-- 6. DSA Banks
CREATE TABLE dsa_banks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dsa_id INT NOT NULL,
    bank_name VARCHAR(150) NOT NULL,
    FOREIGN KEY (dsa_id) REFERENCES dsa_profiles(dsa_id)
        ON DELETE CASCADE
);

-- 7. Reviews
CREATE TABLE reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    dsa_id INT NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dsa_id) REFERENCES dsa_profiles(dsa_id)
        ON DELETE CASCADE,
    CHECK (rating BETWEEN 1 AND 5)
);

-- 8. OTP Verification
CREATE TABLE otp_verification (
    otp_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    otp VARCHAR(10) NOT NULL,
    expires_at DATETIME NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- Loan categories
INSERT INTO loan_types (loan_name, description) VALUES
('Personal Loan', 'Personal loan'),
('Business Loan', 'Business loan'),
('Home Loan', 'Home loan'),
('Loan Against Property', 'Loan against property'),
('Car Loan', 'Car loan');