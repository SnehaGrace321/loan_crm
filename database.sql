CREATE DATABASE IF NOT EXISTS loan_crm;
USE loan_crm;

-- Users: Admin and Staff accounts
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'staff') NOT NULL,
    daily_target INT DEFAULT 100,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Loan leads / customers
CREATE TABLE IF NOT EXISTS leads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(150),
    city VARCHAR(100),
    loan_type VARCHAR(50),
    loan_amount DECIMAL(12,2),
    source VARCHAR(50),
    status ENUM(
        'new',
        'assigned',
        'interested',
        'not_interested',
        'follow_up',
        'converted',
        'closed'
    ) DEFAULT 'new',
    assigned_to INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_leads_assigned_to
        FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- Call history
CREATE TABLE IF NOT EXISTS calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lead_id INT NOT NULL,
    staff_id INT NOT NULL,
    call_status ENUM(
        'connected',
        'not_connected',
        'busy',
        'switched_off'
    ) DEFAULT 'connected',
    interest_status ENUM(
        'interested',
        'not_interested',
        'follow_up',
        'pending'
    ) DEFAULT 'pending',
    remarks TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_calls_lead
        FOREIGN KEY (lead_id) REFERENCES leads(id),
    CONSTRAINT fk_calls_staff
        FOREIGN KEY (staff_id) REFERENCES users(id)
);

-- Loan applications
CREATE TABLE IF NOT EXISTS loan_applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lead_id INT NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    loan_type VARCHAR(50),
    application_number VARCHAR(100),
    loan_amount DECIMAL(12,2),
    status ENUM(
        'draft',
        'submitted',
        'under_review',
        'documents_pending',
        'approved',
        'rejected',
        'disbursed',
        'closed'
    ) DEFAULT 'draft',
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_loan_applications_lead
        FOREIGN KEY (lead_id) REFERENCES leads(id)
);

-- Sample lead data
INSERT INTO leads
(customer_name, phone, email, city, loan_type, loan_amount, source, status)
VALUES
('Rahul Thomas', '9876543210', 'rahul@gmail.com', 'Kochi',
 'Personal Loan', 300000, 'Website', 'new'),
('Anjali Nair', '9876543211', 'anjali@gmail.com', 'Thrissur',
 'Home Loan', 2500000, 'Facebook', 'interested'),
('Arun Kumar', '9876543212', 'arun@gmail.com', 'Kozhikode',
 'Business Loan', 1000000, 'Referral', 'follow_up');

-- Sample loan application
INSERT INTO loan_applications
(lead_id, bank_name, loan_type, application_number, loan_amount, status, remarks)
VALUES
(2, 'ABC Bank', 'Home Loan', 'APP001', 2500000,
 'approved', 'Loan approved');
