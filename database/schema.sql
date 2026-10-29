-- TigerTown MySQL schema. Structure only; contains no survey response rows.
-- MySQL 8.0.16+. Run once against a fresh database.

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS tigertown
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tigertown;

CREATE TABLE survey_sources (
    source_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(512) NOT NULL,
    sha256 VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    response_count INT NOT NULL,
    source_notes TEXT NOT NULL,
    CHECK(CHAR_LENGTH(sha256) = 64),
    CHECK(response_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE survey_responses (
    response_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL,
    source_row_number INT NOT NULL,
    submitted_at_raw VARCHAR(32) NOT NULL,
    classification VARCHAR(64) NOT NULL,
    familiarity_score TINYINT NOT NULL,
    interests_raw TEXT NOT NULL,
    exploration_frequency VARCHAR(32) NOT NULL,
    exploration_barrier VARCHAR(128) NOT NULL,
    price_importance_score TINYINT NOT NULL,
    app_interest VARCHAR(32) NOT NULL,
    desired_information_raw TEXT NOT NULL,
    favorite_place_raw TEXT,
    desired_places_raw TEXT,
    UNIQUE(source_id, source_row_number),
    FOREIGN KEY(source_id) REFERENCES survey_sources(source_id),
    CHECK(source_row_number >= 2),
    CHECK(familiarity_score BETWEEN 1 AND 5),
    CHECK(price_importance_score BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE categories (
    category_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(128) NOT NULL UNIQUE,
    is_survey_option TINYINT NOT NULL,
    CHECK(is_survey_option IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE response_interests (
    response_id INT NOT NULL,
    category_id INT NOT NULL,
    PRIMARY KEY(response_id, category_id),
    FOREIGN KEY(response_id) REFERENCES survey_responses(response_id),
    FOREIGN KEY(category_id) REFERENCES categories(category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE information_fields (
    information_field_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    field_name VARCHAR(128) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE response_information_preferences (
    response_id INT NOT NULL,
    information_field_id INT NOT NULL,
    PRIMARY KEY(response_id, information_field_id),
    FOREIGN KEY(response_id) REFERENCES survey_responses(response_id),
    FOREIGN KEY(information_field_id) REFERENCES information_fields(information_field_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE places (
    place_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL UNIQUE,
    place_kind VARCHAR(32) NOT NULL,
    reported_area VARCHAR(255),
    identity_notes TEXT NOT NULL,
    verification_status VARCHAR(24) NOT NULL DEFAULT 'unverified',
    street_address VARCHAR(255),
    city VARCHAR(128),
    state_code VARCHAR(2),
    postal_code VARCHAR(16),
    latitude DECIMAL(9,6),
    longitude DECIMAL(10,6),
    website_url TEXT,
    hours_summary TEXT,
    menu_services TEXT,
    student_discount_summary TEXT,
    price_min_usd DECIMAL(10,2),
    price_max_usd DECIMAL(10,2),
    price_basis VARCHAR(255),
    verification_source_url TEXT,
    verified_at DATETIME,
    CHECK(place_kind IN ('business','neighborhood','shopping_area','outdoor_area',
                        'library','sports_venue','museum','unspecified_place')),
    CHECK(verification_status IN ('unverified','needs_clarification','verified')),
    CHECK(state_code IS NULL OR CHAR_LENGTH(state_code) = 2),
    CHECK(latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK(longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CHECK((latitude IS NULL AND longitude IS NULL) OR
          (latitude IS NOT NULL AND longitude IS NOT NULL)),
    CHECK(price_min_usd IS NULL OR price_min_usd >= 0),
    CHECK(price_max_usd IS NULL OR price_max_usd >= 0),
    CHECK(price_min_usd IS NULL OR price_max_usd IS NULL OR price_min_usd <= price_max_usd),
    CHECK(verification_status <> 'verified' OR
          (verification_source_url IS NOT NULL AND verified_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE place_aliases (
    place_id INT NOT NULL,
    alias VARCHAR(255) NOT NULL,
    PRIMARY KEY(place_id, alias),
    FOREIGN KEY(place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE place_categories (
    place_id INT NOT NULL,
    category_id INT NOT NULL,
    mapping_basis TEXT NOT NULL,
    PRIMARY KEY(place_id, category_id),
    FOREIGN KEY(place_id) REFERENCES places(place_id),
    FOREIGN KEY(category_id) REFERENCES categories(category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE place_mentions (
    response_id INT NOT NULL,
    place_id INT NOT NULL,
    response_field VARCHAR(24) NOT NULL,
    PRIMARY KEY(response_id, place_id, response_field),
    FOREIGN KEY(response_id) REFERENCES survey_responses(response_id),
    FOREIGN KEY(place_id) REFERENCES places(place_id),
    CHECK(response_field IN ('favorite_place','desired_places'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE requested_venues (
    requested_venue_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    reported_name VARCHAR(255) NOT NULL UNIQUE,
    request_notes TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE requested_venue_mentions (
    response_id INT NOT NULL,
    requested_venue_id INT NOT NULL,
    matched_text VARCHAR(255) NOT NULL,
    PRIMARY KEY(response_id, requested_venue_id),
    FOREIGN KEY(response_id) REFERENCES survey_responses(response_id),
    FOREIGN KEY(requested_venue_id) REFERENCES requested_venues(requested_venue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Intentionally empty: survey familiarity/price scores are not place ratings.
CREATE TABLE place_reviews (
    review_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    place_id INT NOT NULL,
    rating TINYINT NOT NULL,
    review_text TEXT,
    review_source VARCHAR(255) NOT NULL,
    reviewed_at DATETIME NOT NULL,
    FOREIGN KEY(place_id) REFERENCES places(place_id),
    CHECK(rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_places_verification ON places(verification_status);
CREATE INDEX idx_place_categories_category ON place_categories(category_id, place_id);
CREATE INDEX idx_place_mentions_place ON place_mentions(place_id, response_field, response_id);
CREATE INDEX idx_response_interests_category ON response_interests(category_id, response_id);
CREATE INDEX idx_response_information_field ON response_information_preferences(information_field_id, response_id);
CREATE INDEX idx_requested_mentions_venue ON requested_venue_mentions(requested_venue_id, response_id);
CREATE INDEX idx_reviews_place ON place_reviews(place_id);

-- REUSABLE VIEWS (created before starting the seed transaction)

-- Aggregate mentions before joining categories so category links cannot inflate votes.
CREATE VIEW v_place_popularity AS
SELECT p.place_id, p.display_name, p.verification_status,
       COUNT(DISTINCT CASE WHEN m.response_field = 'favorite_place' THEN m.response_id END) AS favorite_respondents,
       COUNT(DISTINCT CASE WHEN m.response_field = 'desired_places' THEN m.response_id END) AS wish_reference_respondents
FROM places AS p
LEFT JOIN place_mentions AS m ON m.place_id = p.place_id
GROUP BY p.place_id, p.display_name, p.verification_status;

CREATE VIEW v_place_directory AS
SELECT p.place_id, p.display_name, p.place_kind, p.verification_status,
       p.reported_area, p.city, p.street_address, p.website_url,
       p.hours_summary, p.menu_services, p.student_discount_summary,
       p.price_min_usd, p.price_max_usd, p.price_basis, p.identity_notes,
       (SELECT GROUP_CONCAT(c.category_name ORDER BY c.category_name SEPARATOR ', ')
        FROM place_categories AS pc JOIN categories AS c USING(category_id)
        WHERE pc.place_id = p.place_id) AS categories,
       pop.favorite_respondents,
       (SELECT ROUND(AVG(r.rating),2) FROM place_reviews AS r
        WHERE r.place_id = p.place_id) AS average_place_rating
FROM places AS p
JOIN v_place_popularity AS pop USING(place_id);

-- Empty initially. Only independently verified entries belong in public recommendations.
CREATE VIEW v_verified_places AS
SELECT * FROM v_place_directory WHERE verification_status = 'verified';

-- Multi-select percentages use all survey responses as the denominator.
-- They can sum above 100 percent because a respondent may choose several categories.
CREATE VIEW v_category_demand AS
SELECT c.category_id, c.category_name, COUNT(ri.response_id) AS interested_respondents,
       ROUND(100.0 * COUNT(ri.response_id) /
             NULLIF((SELECT COUNT(*) FROM survey_responses),0),1) AS percent_of_respondents
FROM categories AS c
LEFT JOIN response_interests AS ri USING(category_id)
WHERE c.is_survey_option = 1
GROUP BY c.category_id, c.category_name;

CREATE VIEW v_information_demand AS
SELECT f.information_field_id, f.field_name, COUNT(rip.response_id) AS interested_respondents,
       ROUND(100.0 * COUNT(rip.response_id) /
             NULLIF((SELECT COUNT(*) FROM survey_responses),0),1) AS percent_of_respondents
FROM information_fields AS f
LEFT JOIN response_information_preferences AS rip USING(information_field_id)
GROUP BY f.information_field_id, f.field_name;

CREATE VIEW v_exploration_barriers AS
SELECT exploration_barrier, COUNT(*) AS respondents,
       ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM survey_responses),0),1) AS percent_of_respondents
FROM survey_responses GROUP BY exploration_barrier;

CREATE VIEW v_requested_venues AS
SELECT v.requested_venue_id, v.reported_name, v.request_notes,
       COUNT(m.response_id) AS requesting_respondents
FROM requested_venues AS v
LEFT JOIN requested_venue_mentions AS m USING(requested_venue_id)
GROUP BY v.requested_venue_id, v.reported_name, v.request_notes;

CREATE VIEW v_place_source_evidence AS
SELECT p.place_id, p.display_name, s.file_name, r.source_row_number,
       m.response_field,
       CASE m.response_field WHEN 'favorite_place' THEN r.favorite_place_raw
            ELSE r.desired_places_raw END AS original_response
FROM place_mentions AS m
JOIN places AS p USING(place_id)
JOIN survey_responses AS r USING(response_id)
JOIN survey_sources AS s USING(source_id);

-- SURVEY SEED DATA

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tigertown;

CREATE TABLE IF NOT EXISTS place_research (
    place_id INT NOT NULL PRIMARY KEY,
    canonical_name VARCHAR(255),
    identity_status VARCHAR(24) NOT NULL,
    research_notes TEXT NOT NULL,
    primary_source_url TEXT,
    checked_on DATE NOT NULL,
    FOREIGN KEY (place_id) REFERENCES places(place_id),
    CHECK (identity_status IN ('verified','needs_clarification'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS place_research_fields (
    place_id INT NOT NULL,
    field_name VARCHAR(64) NOT NULL,
    research_status VARCHAR(24) NOT NULL,
    researched_value TEXT,
    source_url TEXT,
    checked_on DATE NOT NULL,
    notes TEXT NOT NULL,
    PRIMARY KEY (place_id, field_name),
    FOREIGN KEY (place_id) REFERENCES places(place_id),
    CHECK (research_status IN ('published','partial','not_published','not_applicable','unresolved','conflicting'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS place_branches (
    branch_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    place_id INT NOT NULL,
    branch_key VARCHAR(64) NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    street_address VARCHAR(255) NOT NULL,
    city VARCHAR(128) NOT NULL,
    state_code VARCHAR(2) NOT NULL,
    postal_code VARCHAR(16),
    latitude DECIMAL(9,6),
    longitude DECIMAL(10,6),
    website_url TEXT,
    hours_summary TEXT,
    menu_services TEXT,
    phone VARCHAR(48),
    student_discount_summary TEXT,
    price_min_usd DECIMAL(10,2),
    price_max_usd DECIMAL(10,2),
    price_basis VARCHAR(255),
    price_source_url TEXT,
    source_url TEXT NOT NULL,
    checked_on DATE NOT NULL,
    notes TEXT NOT NULL,
    UNIQUE (place_id, branch_key),
    FOREIGN KEY (place_id) REFERENCES places(place_id),
    CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CHECK (price_min_usd IS NULL OR price_min_usd >= 0),
    CHECK (price_max_usd IS NULL OR price_max_usd >= 0),
    CHECK (price_min_usd IS NULL OR price_max_usd IS NULL OR price_min_usd <= price_max_usd)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS place_identity_candidates (
    candidate_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    place_id INT NOT NULL,
    candidate_key VARCHAR(64) NOT NULL,
    candidate_name VARCHAR(255) NOT NULL,
    street_address VARCHAR(255),
    city VARCHAR(128),
    state_code VARCHAR(2),
    postal_code VARCHAR(16),
    website_url TEXT,
    hours_summary TEXT,
    menu_services TEXT,
    price_min_usd DECIMAL(10,2),
    price_max_usd DECIMAL(10,2),
    price_basis VARCHAR(255),
    price_source_url TEXT,
    source_url TEXT NOT NULL,
    checked_on DATE NOT NULL,
    notes TEXT NOT NULL,
    UNIQUE (place_id, candidate_key),
    FOREIGN KEY (place_id) REFERENCES places(place_id),
    CHECK (price_min_usd IS NULL OR price_min_usd >= 0),
    CHECK (price_max_usd IS NULL OR price_max_usd >= 0),
    CHECK (price_min_usd IS NULL OR price_max_usd IS NULL OR price_min_usd <= price_max_usd)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE OR REPLACE VIEW v_place_research_directory AS
SELECT p.*, r.canonical_name AS researched_name, r.identity_status AS researched_identity_status,
       r.research_notes, r.checked_on AS research_checked_on
FROM places p LEFT JOIN place_research r ON r.place_id = p.place_id;

