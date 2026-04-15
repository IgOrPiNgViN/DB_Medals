--
-- PostgreSQL database dump
--

\restrict nd4S50w4caSF61RYmxxev30bLSkFK0iLpBvXeeVu8zHaqJDeWn28TjqCEBXNQja

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: approvaltype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.approvaltype AS ENUM (
    'NK',
    'HERALDISTS',
    'RELATIVES',
    'SPONSORS'
);


ALTER TYPE public.approvaltype OWNER TO postgres;

--
-- Name: awardtype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.awardtype AS ENUM (
    'MEDAL',
    'PPZ',
    'DISTINCTION',
    'DECORATION'
);


ALTER TYPE public.awardtype OWNER TO postgres;

--
-- Name: bulletinstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.bulletinstatus AS ENUM (
    'DRAFT',
    'ACTIVE',
    'CLOSED'
);


ALTER TYPE public.bulletinstatus OWNER TO postgres;

--
-- Name: bulletintype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.bulletintype AS ENUM (
    'MEDAL',
    'PPZ'
);


ALTER TYPE public.bulletintype OWNER TO postgres;

--
-- Name: componenttype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.componenttype AS ENUM (
    'MEDAL',
    'BADGE',
    'CUFFLINKS',
    'PENDANT',
    'PPZ',
    'BOX',
    'CERTIFICATE',
    'CASE'
);


ALTER TYPE public.componenttype OWNER TO postgres;

--
-- Name: laureatecategory; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.laureatecategory AS ENUM (
    'EMPLOYEE',
    'VETERAN',
    'UNIVERSITY',
    'NII',
    'NONPROFIT',
    'COMMERCIAL'
);


ALTER TYPE public.laureatecategory OWNER TO postgres;

--
-- Name: protocolstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.protocolstatus AS ENUM (
    'DRAFT',
    'SIGNED'
);


ALTER TYPE public.protocolstatus OWNER TO postgres;

--
-- Name: signingrole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.signingrole AS ENUM (
    'SIGNER',
    'AUTHORIZED'
);


ALTER TYPE public.signingrole OWNER TO postgres;

--
-- Name: votevalue; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.votevalue AS ENUM (
    'FOR',
    'AGAINST'
);


ALTER TYPE public.votevalue OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_mirror_rows; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.access_mirror_rows (
    id integer NOT NULL,
    table_name character varying(512) NOT NULL,
    row_index integer NOT NULL,
    data jsonb NOT NULL
);


ALTER TABLE public.access_mirror_rows OWNER TO postgres;

--
-- Name: access_mirror_rows_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.access_mirror_rows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.access_mirror_rows_id_seq OWNER TO postgres;

--
-- Name: access_mirror_rows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.access_mirror_rows_id_seq OWNED BY public.access_mirror_rows.id;


--
-- Name: award_approvals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.award_approvals (
    id integer NOT NULL,
    award_id integer NOT NULL,
    approval_type public.approvaltype NOT NULL,
    approver_name character varying(500),
    status character varying(100),
    date date,
    details text
);


ALTER TABLE public.award_approvals OWNER TO postgres;

--
-- Name: award_approvals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.award_approvals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.award_approvals_id_seq OWNER TO postgres;

--
-- Name: award_approvals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.award_approvals_id_seq OWNED BY public.award_approvals.id;


--
-- Name: award_characteristics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.award_characteristics (
    id integer NOT NULL,
    award_id integer NOT NULL,
    field_name character varying(255) NOT NULL,
    field_value text
);


ALTER TABLE public.award_characteristics OWNER TO postgres;

--
-- Name: award_characteristics_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.award_characteristics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.award_characteristics_id_seq OWNER TO postgres;

--
-- Name: award_characteristics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.award_characteristics_id_seq OWNED BY public.award_characteristics.id;


--
-- Name: award_developments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.award_developments (
    id integer NOT NULL,
    award_id integer NOT NULL,
    developer character varying(500),
    start_date date,
    end_date date,
    status character varying(100),
    details text
);


ALTER TABLE public.award_developments OWNER TO postgres;

--
-- Name: award_developments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.award_developments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.award_developments_id_seq OWNER TO postgres;

--
-- Name: award_developments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.award_developments_id_seq OWNED BY public.award_developments.id;


--
-- Name: award_establishments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.award_establishments (
    id integer NOT NULL,
    award_id integer NOT NULL,
    establishment_date date,
    document_number character varying(100),
    document_date date,
    initiator character varying(500),
    details text
);


ALTER TABLE public.award_establishments OWNER TO postgres;

--
-- Name: award_establishments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.award_establishments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.award_establishments_id_seq OWNER TO postgres;

--
-- Name: award_establishments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.award_establishments_id_seq OWNED BY public.award_establishments.id;


--
-- Name: award_productions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.award_productions (
    id integer NOT NULL,
    award_id integer NOT NULL,
    component_type public.componenttype NOT NULL,
    supplier character varying(500),
    quantity integer,
    unit_price double precision,
    order_date date,
    delivery_date date,
    status character varying(100),
    details text
);


ALTER TABLE public.award_productions OWNER TO postgres;

--
-- Name: award_productions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.award_productions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.award_productions_id_seq OWNER TO postgres;

--
-- Name: award_productions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.award_productions_id_seq OWNED BY public.award_productions.id;


--
-- Name: awards; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.awards (
    id integer NOT NULL,
    name character varying(500) NOT NULL,
    award_type public.awardtype NOT NULL,
    description text,
    image_front bytea,
    image_back bytea,
    created_at timestamp without time zone
);


ALTER TABLE public.awards OWNER TO postgres;

--
-- Name: awards_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.awards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.awards_id_seq OWNER TO postgres;

--
-- Name: awards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.awards_id_seq OWNED BY public.awards.id;


--
-- Name: bulletin_distributions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bulletin_distributions (
    id integer NOT NULL,
    bulletin_id integer NOT NULL,
    member_id integer NOT NULL,
    sent boolean,
    sent_date date,
    received boolean,
    received_date date
);


ALTER TABLE public.bulletin_distributions OWNER TO postgres;

--
-- Name: bulletin_distributions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bulletin_distributions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bulletin_distributions_id_seq OWNER TO postgres;

--
-- Name: bulletin_distributions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bulletin_distributions_id_seq OWNED BY public.bulletin_distributions.id;


--
-- Name: bulletin_questions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bulletin_questions (
    id integer NOT NULL,
    section_id integer NOT NULL,
    question_text text NOT NULL,
    question_order integer,
    laureate_award_id integer,
    initiator character varying(500)
);


ALTER TABLE public.bulletin_questions OWNER TO postgres;

--
-- Name: bulletin_questions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bulletin_questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bulletin_questions_id_seq OWNER TO postgres;

--
-- Name: bulletin_questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bulletin_questions_id_seq OWNED BY public.bulletin_questions.id;


--
-- Name: bulletin_sections; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bulletin_sections (
    id integer NOT NULL,
    bulletin_id integer NOT NULL,
    section_name character varying(500) NOT NULL,
    section_order integer
);


ALTER TABLE public.bulletin_sections OWNER TO postgres;

--
-- Name: bulletin_sections_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bulletin_sections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bulletin_sections_id_seq OWNER TO postgres;

--
-- Name: bulletin_sections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bulletin_sections_id_seq OWNED BY public.bulletin_sections.id;


--
-- Name: bulletins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bulletins (
    id integer NOT NULL,
    number character varying(50) NOT NULL,
    bulletin_type public.bulletintype NOT NULL,
    voting_start date,
    voting_end date,
    postal_address text,
    status public.bulletinstatus,
    created_at timestamp without time zone
);


ALTER TABLE public.bulletins OWNER TO postgres;

--
-- Name: bulletins_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bulletins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bulletins_id_seq OWNER TO postgres;

--
-- Name: bulletins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bulletins_id_seq OWNED BY public.bulletins.id;


--
-- Name: committee_members; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.committee_members (
    id integer NOT NULL,
    full_name character varying(500) NOT NULL,
    "position" character varying(500),
    organization character varying(500),
    phone character varying(100),
    email character varying(255),
    is_active boolean,
    notes text,
    created_at timestamp without time zone
);


ALTER TABLE public.committee_members OWNER TO postgres;

--
-- Name: committee_members_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.committee_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.committee_members_id_seq OWNER TO postgres;

--
-- Name: committee_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.committee_members_id_seq OWNED BY public.committee_members.id;


--
-- Name: inventory_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_items (
    id integer NOT NULL,
    award_id integer NOT NULL,
    component_type public.componenttype NOT NULL,
    total_count integer,
    reserve_count integer,
    issued_count integer,
    available_count integer,
    details text,
    updated_at timestamp without time zone
);


ALTER TABLE public.inventory_items OWNER TO postgres;

--
-- Name: inventory_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_items_id_seq OWNER TO postgres;

--
-- Name: inventory_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_items_id_seq OWNED BY public.inventory_items.id;


--
-- Name: laureate_awards; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.laureate_awards (
    id integer NOT NULL,
    laureate_id integer NOT NULL,
    award_id integer NOT NULL,
    assigned_date date,
    bulletin_number character varying(50),
    initiator character varying(500),
    status character varying(100)
);


ALTER TABLE public.laureate_awards OWNER TO postgres;

--
-- Name: laureate_awards_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.laureate_awards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laureate_awards_id_seq OWNER TO postgres;

--
-- Name: laureate_awards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.laureate_awards_id_seq OWNED BY public.laureate_awards.id;


--
-- Name: laureate_consent_files; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.laureate_consent_files (
    id integer NOT NULL,
    laureate_award_id integer NOT NULL,
    filename character varying(500) NOT NULL,
    content_type character varying(200),
    data bytea NOT NULL,
    uploaded_at timestamp without time zone
);


ALTER TABLE public.laureate_consent_files OWNER TO postgres;

--
-- Name: laureate_consent_files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.laureate_consent_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laureate_consent_files_id_seq OWNER TO postgres;

--
-- Name: laureate_consent_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.laureate_consent_files_id_seq OWNED BY public.laureate_consent_files.id;


--
-- Name: laureate_lifecycles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.laureate_lifecycles (
    id integer NOT NULL,
    laureate_award_id integer NOT NULL,
    nomination_date date,
    nomination_initiator character varying(500),
    nomination_done boolean,
    voting_date date,
    voting_bulletin_number character varying(50),
    voting_done boolean,
    decision_date date,
    decision_protocol_number character varying(50),
    decision_done boolean,
    registration_date date,
    registration_signer_id integer,
    registration_certificate_number character varying(100),
    registration_done boolean,
    ceremony_date date,
    ceremony_place character varying(500),
    ceremony_done boolean,
    publication_date date,
    publication_source character varying(500),
    publication_done boolean,
    inventory_reserved boolean,
    inventory_issued boolean,
    consent_sent_date date,
    consent_received_date date,
    consent_received boolean DEFAULT false
);


ALTER TABLE public.laureate_lifecycles OWNER TO postgres;

--
-- Name: laureate_lifecycles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.laureate_lifecycles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laureate_lifecycles_id_seq OWNER TO postgres;

--
-- Name: laureate_lifecycles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.laureate_lifecycles_id_seq OWNED BY public.laureate_lifecycles.id;


--
-- Name: laureates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.laureates (
    id integer NOT NULL,
    full_name character varying(500) NOT NULL,
    category public.laureatecategory,
    "position" character varying(500),
    organization character varying(500),
    phone character varying(100),
    email character varying(255),
    address text,
    notes text,
    created_at timestamp without time zone
);


ALTER TABLE public.laureates OWNER TO postgres;

--
-- Name: laureates_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.laureates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laureates_id_seq OWNER TO postgres;

--
-- Name: laureates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.laureates_id_seq OWNED BY public.laureates.id;


--
-- Name: member_signing_rights; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.member_signing_rights (
    id integer NOT NULL,
    member_id integer NOT NULL,
    award_id integer NOT NULL,
    role public.signingrole NOT NULL,
    assigned_date date
);


ALTER TABLE public.member_signing_rights OWNER TO postgres;

--
-- Name: member_signing_rights_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.member_signing_rights_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.member_signing_rights_id_seq OWNER TO postgres;

--
-- Name: member_signing_rights_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.member_signing_rights_id_seq OWNED BY public.member_signing_rights.id;


--
-- Name: ppz_submissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ppz_submissions (
    id integer NOT NULL,
    laureate_award_id integer NOT NULL,
    authorized_member_id integer NOT NULL,
    submission_number character varying(50),
    date date,
    details text
);


ALTER TABLE public.ppz_submissions OWNER TO postgres;

--
-- Name: ppz_submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ppz_submissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ppz_submissions_id_seq OWNER TO postgres;

--
-- Name: ppz_submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ppz_submissions_id_seq OWNED BY public.ppz_submissions.id;


--
-- Name: protocol_extracts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.protocol_extracts (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    laureate_award_id integer NOT NULL,
    extract_date date,
    details text
);


ALTER TABLE public.protocol_extracts OWNER TO postgres;

--
-- Name: protocol_extracts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.protocol_extracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.protocol_extracts_id_seq OWNER TO postgres;

--
-- Name: protocol_extracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.protocol_extracts_id_seq OWNED BY public.protocol_extracts.id;


--
-- Name: protocols; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.protocols (
    id integer NOT NULL,
    bulletin_id integer NOT NULL,
    number character varying(50) NOT NULL,
    date date,
    status public.protocolstatus,
    details text,
    created_at timestamp without time zone
);


ALTER TABLE public.protocols OWNER TO postgres;

--
-- Name: protocols_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.protocols_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.protocols_id_seq OWNER TO postgres;

--
-- Name: protocols_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.protocols_id_seq OWNED BY public.protocols.id;


--
-- Name: votes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.votes (
    id integer NOT NULL,
    question_id integer NOT NULL,
    member_id integer NOT NULL,
    value public.votevalue,
    voted_at timestamp without time zone
);


ALTER TABLE public.votes OWNER TO postgres;

--
-- Name: votes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.votes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.votes_id_seq OWNER TO postgres;

--
-- Name: votes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.votes_id_seq OWNED BY public.votes.id;


--
-- Name: access_mirror_rows id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_mirror_rows ALTER COLUMN id SET DEFAULT nextval('public.access_mirror_rows_id_seq'::regclass);


--
-- Name: award_approvals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_approvals ALTER COLUMN id SET DEFAULT nextval('public.award_approvals_id_seq'::regclass);


--
-- Name: award_characteristics id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_characteristics ALTER COLUMN id SET DEFAULT nextval('public.award_characteristics_id_seq'::regclass);


--
-- Name: award_developments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_developments ALTER COLUMN id SET DEFAULT nextval('public.award_developments_id_seq'::regclass);


--
-- Name: award_establishments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_establishments ALTER COLUMN id SET DEFAULT nextval('public.award_establishments_id_seq'::regclass);


--
-- Name: award_productions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_productions ALTER COLUMN id SET DEFAULT nextval('public.award_productions_id_seq'::regclass);


--
-- Name: awards id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.awards ALTER COLUMN id SET DEFAULT nextval('public.awards_id_seq'::regclass);


--
-- Name: bulletin_distributions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_distributions ALTER COLUMN id SET DEFAULT nextval('public.bulletin_distributions_id_seq'::regclass);


--
-- Name: bulletin_questions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_questions ALTER COLUMN id SET DEFAULT nextval('public.bulletin_questions_id_seq'::regclass);


--
-- Name: bulletin_sections id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_sections ALTER COLUMN id SET DEFAULT nextval('public.bulletin_sections_id_seq'::regclass);


--
-- Name: bulletins id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletins ALTER COLUMN id SET DEFAULT nextval('public.bulletins_id_seq'::regclass);


--
-- Name: committee_members id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.committee_members ALTER COLUMN id SET DEFAULT nextval('public.committee_members_id_seq'::regclass);


--
-- Name: inventory_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_items ALTER COLUMN id SET DEFAULT nextval('public.inventory_items_id_seq'::regclass);


--
-- Name: laureate_awards id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_awards ALTER COLUMN id SET DEFAULT nextval('public.laureate_awards_id_seq'::regclass);


--
-- Name: laureate_consent_files id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_consent_files ALTER COLUMN id SET DEFAULT nextval('public.laureate_consent_files_id_seq'::regclass);


--
-- Name: laureate_lifecycles id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_lifecycles ALTER COLUMN id SET DEFAULT nextval('public.laureate_lifecycles_id_seq'::regclass);


--
-- Name: laureates id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureates ALTER COLUMN id SET DEFAULT nextval('public.laureates_id_seq'::regclass);


--
-- Name: member_signing_rights id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.member_signing_rights ALTER COLUMN id SET DEFAULT nextval('public.member_signing_rights_id_seq'::regclass);


--
-- Name: ppz_submissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ppz_submissions ALTER COLUMN id SET DEFAULT nextval('public.ppz_submissions_id_seq'::regclass);


--
-- Name: protocol_extracts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocol_extracts ALTER COLUMN id SET DEFAULT nextval('public.protocol_extracts_id_seq'::regclass);


--
-- Name: protocols id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocols ALTER COLUMN id SET DEFAULT nextval('public.protocols_id_seq'::regclass);


--
-- Name: votes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.votes ALTER COLUMN id SET DEFAULT nextval('public.votes_id_seq'::regclass);


--
-- Name: access_mirror_rows access_mirror_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_mirror_rows
    ADD CONSTRAINT access_mirror_rows_pkey PRIMARY KEY (id);


--
-- Name: award_approvals award_approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_approvals
    ADD CONSTRAINT award_approvals_pkey PRIMARY KEY (id);


--
-- Name: award_characteristics award_characteristics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_characteristics
    ADD CONSTRAINT award_characteristics_pkey PRIMARY KEY (id);


--
-- Name: award_developments award_developments_award_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_developments
    ADD CONSTRAINT award_developments_award_id_key UNIQUE (award_id);


--
-- Name: award_developments award_developments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_developments
    ADD CONSTRAINT award_developments_pkey PRIMARY KEY (id);


--
-- Name: award_establishments award_establishments_award_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_establishments
    ADD CONSTRAINT award_establishments_award_id_key UNIQUE (award_id);


--
-- Name: award_establishments award_establishments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_establishments
    ADD CONSTRAINT award_establishments_pkey PRIMARY KEY (id);


--
-- Name: award_productions award_productions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_productions
    ADD CONSTRAINT award_productions_pkey PRIMARY KEY (id);


--
-- Name: awards awards_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.awards
    ADD CONSTRAINT awards_pkey PRIMARY KEY (id);


--
-- Name: bulletin_distributions bulletin_distributions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_distributions
    ADD CONSTRAINT bulletin_distributions_pkey PRIMARY KEY (id);


--
-- Name: bulletin_questions bulletin_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_questions
    ADD CONSTRAINT bulletin_questions_pkey PRIMARY KEY (id);


--
-- Name: bulletin_sections bulletin_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_sections
    ADD CONSTRAINT bulletin_sections_pkey PRIMARY KEY (id);


--
-- Name: bulletins bulletins_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletins
    ADD CONSTRAINT bulletins_number_key UNIQUE (number);


--
-- Name: bulletins bulletins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletins
    ADD CONSTRAINT bulletins_pkey PRIMARY KEY (id);


--
-- Name: committee_members committee_members_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.committee_members
    ADD CONSTRAINT committee_members_pkey PRIMARY KEY (id);


--
-- Name: inventory_items inventory_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_items
    ADD CONSTRAINT inventory_items_pkey PRIMARY KEY (id);


--
-- Name: laureate_awards laureate_awards_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_awards
    ADD CONSTRAINT laureate_awards_pkey PRIMARY KEY (id);


--
-- Name: laureate_consent_files laureate_consent_files_laureate_award_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_consent_files
    ADD CONSTRAINT laureate_consent_files_laureate_award_id_key UNIQUE (laureate_award_id);


--
-- Name: laureate_consent_files laureate_consent_files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_consent_files
    ADD CONSTRAINT laureate_consent_files_pkey PRIMARY KEY (id);


--
-- Name: laureate_lifecycles laureate_lifecycles_laureate_award_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_lifecycles
    ADD CONSTRAINT laureate_lifecycles_laureate_award_id_key UNIQUE (laureate_award_id);


--
-- Name: laureate_lifecycles laureate_lifecycles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_lifecycles
    ADD CONSTRAINT laureate_lifecycles_pkey PRIMARY KEY (id);


--
-- Name: laureates laureates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureates
    ADD CONSTRAINT laureates_pkey PRIMARY KEY (id);


--
-- Name: member_signing_rights member_signing_rights_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.member_signing_rights
    ADD CONSTRAINT member_signing_rights_pkey PRIMARY KEY (id);


--
-- Name: ppz_submissions ppz_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ppz_submissions
    ADD CONSTRAINT ppz_submissions_pkey PRIMARY KEY (id);


--
-- Name: protocol_extracts protocol_extracts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocol_extracts
    ADD CONSTRAINT protocol_extracts_pkey PRIMARY KEY (id);


--
-- Name: protocols protocols_bulletin_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocols
    ADD CONSTRAINT protocols_bulletin_id_key UNIQUE (bulletin_id);


--
-- Name: protocols protocols_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocols
    ADD CONSTRAINT protocols_pkey PRIMARY KEY (id);


--
-- Name: access_mirror_rows uq_access_mirror_table_row; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_mirror_rows
    ADD CONSTRAINT uq_access_mirror_table_row UNIQUE (table_name, row_index);


--
-- Name: votes votes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_pkey PRIMARY KEY (id);


--
-- Name: ix_access_mirror_rows_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_access_mirror_rows_id ON public.access_mirror_rows USING btree (id);


--
-- Name: ix_access_mirror_rows_table_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_access_mirror_rows_table_name ON public.access_mirror_rows USING btree (table_name);


--
-- Name: ix_award_approvals_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_award_approvals_id ON public.award_approvals USING btree (id);


--
-- Name: ix_award_characteristics_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_award_characteristics_id ON public.award_characteristics USING btree (id);


--
-- Name: ix_award_developments_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_award_developments_id ON public.award_developments USING btree (id);


--
-- Name: ix_award_establishments_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_award_establishments_id ON public.award_establishments USING btree (id);


--
-- Name: ix_award_productions_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_award_productions_id ON public.award_productions USING btree (id);


--
-- Name: ix_awards_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_awards_id ON public.awards USING btree (id);


--
-- Name: ix_bulletin_distributions_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_bulletin_distributions_id ON public.bulletin_distributions USING btree (id);


--
-- Name: ix_bulletin_questions_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_bulletin_questions_id ON public.bulletin_questions USING btree (id);


--
-- Name: ix_bulletin_sections_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_bulletin_sections_id ON public.bulletin_sections USING btree (id);


--
-- Name: ix_bulletins_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_bulletins_id ON public.bulletins USING btree (id);


--
-- Name: ix_committee_members_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_committee_members_id ON public.committee_members USING btree (id);


--
-- Name: ix_inventory_items_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_inventory_items_id ON public.inventory_items USING btree (id);


--
-- Name: ix_laureate_awards_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_laureate_awards_id ON public.laureate_awards USING btree (id);


--
-- Name: ix_laureate_consent_files_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_laureate_consent_files_id ON public.laureate_consent_files USING btree (id);


--
-- Name: ix_laureate_lifecycles_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_laureate_lifecycles_id ON public.laureate_lifecycles USING btree (id);


--
-- Name: ix_laureates_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_laureates_id ON public.laureates USING btree (id);


--
-- Name: ix_member_signing_rights_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_member_signing_rights_id ON public.member_signing_rights USING btree (id);


--
-- Name: ix_ppz_submissions_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_ppz_submissions_id ON public.ppz_submissions USING btree (id);


--
-- Name: ix_protocol_extracts_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_protocol_extracts_id ON public.protocol_extracts USING btree (id);


--
-- Name: ix_protocols_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_protocols_id ON public.protocols USING btree (id);


--
-- Name: ix_votes_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_votes_id ON public.votes USING btree (id);


--
-- Name: award_approvals award_approvals_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_approvals
    ADD CONSTRAINT award_approvals_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: award_characteristics award_characteristics_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_characteristics
    ADD CONSTRAINT award_characteristics_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: award_developments award_developments_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_developments
    ADD CONSTRAINT award_developments_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: award_establishments award_establishments_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_establishments
    ADD CONSTRAINT award_establishments_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: award_productions award_productions_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.award_productions
    ADD CONSTRAINT award_productions_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: bulletin_distributions bulletin_distributions_bulletin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_distributions
    ADD CONSTRAINT bulletin_distributions_bulletin_id_fkey FOREIGN KEY (bulletin_id) REFERENCES public.bulletins(id);


--
-- Name: bulletin_distributions bulletin_distributions_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_distributions
    ADD CONSTRAINT bulletin_distributions_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.committee_members(id);


--
-- Name: bulletin_questions bulletin_questions_laureate_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_questions
    ADD CONSTRAINT bulletin_questions_laureate_award_id_fkey FOREIGN KEY (laureate_award_id) REFERENCES public.laureate_awards(id);


--
-- Name: bulletin_questions bulletin_questions_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_questions
    ADD CONSTRAINT bulletin_questions_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.bulletin_sections(id);


--
-- Name: bulletin_sections bulletin_sections_bulletin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bulletin_sections
    ADD CONSTRAINT bulletin_sections_bulletin_id_fkey FOREIGN KEY (bulletin_id) REFERENCES public.bulletins(id);


--
-- Name: inventory_items inventory_items_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_items
    ADD CONSTRAINT inventory_items_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: laureate_awards laureate_awards_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_awards
    ADD CONSTRAINT laureate_awards_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: laureate_awards laureate_awards_laureate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_awards
    ADD CONSTRAINT laureate_awards_laureate_id_fkey FOREIGN KEY (laureate_id) REFERENCES public.laureates(id);


--
-- Name: laureate_consent_files laureate_consent_files_laureate_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_consent_files
    ADD CONSTRAINT laureate_consent_files_laureate_award_id_fkey FOREIGN KEY (laureate_award_id) REFERENCES public.laureate_awards(id);


--
-- Name: laureate_lifecycles laureate_lifecycles_laureate_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_lifecycles
    ADD CONSTRAINT laureate_lifecycles_laureate_award_id_fkey FOREIGN KEY (laureate_award_id) REFERENCES public.laureate_awards(id);


--
-- Name: laureate_lifecycles laureate_lifecycles_registration_signer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laureate_lifecycles
    ADD CONSTRAINT laureate_lifecycles_registration_signer_id_fkey FOREIGN KEY (registration_signer_id) REFERENCES public.committee_members(id);


--
-- Name: member_signing_rights member_signing_rights_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.member_signing_rights
    ADD CONSTRAINT member_signing_rights_award_id_fkey FOREIGN KEY (award_id) REFERENCES public.awards(id);


--
-- Name: member_signing_rights member_signing_rights_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.member_signing_rights
    ADD CONSTRAINT member_signing_rights_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.committee_members(id);


--
-- Name: ppz_submissions ppz_submissions_authorized_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ppz_submissions
    ADD CONSTRAINT ppz_submissions_authorized_member_id_fkey FOREIGN KEY (authorized_member_id) REFERENCES public.committee_members(id);


--
-- Name: ppz_submissions ppz_submissions_laureate_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ppz_submissions
    ADD CONSTRAINT ppz_submissions_laureate_award_id_fkey FOREIGN KEY (laureate_award_id) REFERENCES public.laureate_awards(id);


--
-- Name: protocol_extracts protocol_extracts_laureate_award_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocol_extracts
    ADD CONSTRAINT protocol_extracts_laureate_award_id_fkey FOREIGN KEY (laureate_award_id) REFERENCES public.laureate_awards(id);


--
-- Name: protocol_extracts protocol_extracts_protocol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocol_extracts
    ADD CONSTRAINT protocol_extracts_protocol_id_fkey FOREIGN KEY (protocol_id) REFERENCES public.protocols(id);


--
-- Name: protocols protocols_bulletin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.protocols
    ADD CONSTRAINT protocols_bulletin_id_fkey FOREIGN KEY (bulletin_id) REFERENCES public.bulletins(id);


--
-- Name: votes votes_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.committee_members(id);


--
-- Name: votes votes_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.bulletin_questions(id);


--
-- PostgreSQL database dump complete
--

\unrestrict nd4S50w4caSF61RYmxxev30bLSkFK0iLpBvXeeVu8zHaqJDeWn28TjqCEBXNQja

