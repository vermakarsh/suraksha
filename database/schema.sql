-- Create database
CREATE DATABASE IF NOT EXISTS suraksha_db;
USE suraksha_db;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    mobile_number VARCHAR(15),
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    age INT NOT NULL,
    role ENUM('admin', 'professional') NOT NULL,
    designation VARCHAR(100),
    department VARCHAR(100),
    specialization VARCHAR(100),
    experience_years INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create trainees table
CREATE TABLE IF NOT EXISTS trainees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(15),
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    age INT NOT NULL,
    department VARCHAR(100) NOT NULL,
    designation VARCHAR(100),
    address VARCHAR(200) NOT NULL,
    block ENUM('Raipur', 'Birgaon', 'Abhanpur', 'Arang', 'Dhariswa', 'Tilda') NOT NULL,
    training_date DATE NOT NULL,
    cpr_training BOOLEAN DEFAULT FALSE,
    first_aid_kit_given BOOLEAN DEFAULT FALSE,
    life_saving_skills BOOLEAN DEFAULT FALSE,
    registered_by INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registered_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Create trainings table
CREATE TABLE IF NOT EXISTS trainings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    training_topic VARCHAR(200) NOT NULL,
    address VARCHAR(200) NOT NULL,
    block ENUM('Raipur', 'Birgaon', 'Abhanpur', 'Arang', 'Dhariswa', 'Tilda') NOT NULL,
    training_date DATE NOT NULL,
    training_time TIME NOT NULL,
    duration_hours DECIMAL(3,1) DEFAULT 1.0,
    trainees INT DEFAULT 50,
    current_trainees INT DEFAULT 0,
    status ENUM('Planned', 'Ongoing', 'Completed', 'Cancelled') DEFAULT 'Planned',
    conducted_by INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (conducted_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert default admin user (password: admin123)
INSERT INTO users (name, username, password, mobile_number, gender, age, role, designation, department, specialization, experience_years) VALUES 
('Admin User', 'admin', 'admin123', '9999999999', 'Male', 35, 'admin', 'System Administrator', 'IT Department', 'Healthcare IT', 5),
('Dr. Demo Professional', 'demo', '9876543210', '9876543210', 'Male', 40, 'professional', 'Senior Consultant', 'Emergency Medicine', 'Emergency Care', 10);
