-- Seguridad (repetible: se reaplica cuando cambia este archivo o cuando se aplica una migracion nueva,
-- asi las tablas nuevas quedan cubiertas).
--
-- 1) RLS activado en las tablas de AgroIA: el rol dueno (postgres / el de las migraciones) la omite, asi que el ETL, la web
--    actual y Power BI conectados con ese rol siguen funcionando; en cambio los roles de la API REST de Supabase
--    (anon / authenticated) dejan de ver cualquier fila mientras no exista una politica para ellos.
-- 2) Rol `agroia_web`: solo lectura + escritura unicamente en chat_*. Se crea sin contrasena (no puede iniciar sesion
--    hasta ejecutar `python -m load.migrate --web-password`). Para usarlo, apunta DB_USER/DB_PASSWORD de la web a ese rol.
DO $seguridad$
DECLARE
    t      RECORD;
    v      RECORD;
    web_ok BOOLEAN;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agroia_web') THEN
        BEGIN
            CREATE ROLE agroia_web LOGIN NOINHERIT;
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE NOTICE 'Sin permiso para crear el rol agroia_web: se omite (crealo con un usuario administrador).';
        END;
    END IF;
    web_ok := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agroia_web');

    IF web_ok THEN
        EXECUTE 'GRANT USAGE ON SCHEMA public TO agroia_web';
    END IF;

    FOR t IN
        SELECT c.relname AS nombre
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND (c.relname ~ '^(dim|fact|pred|model|chat|quality|extraction|informe)_' OR c.relname IN ('ingest_run', 'schema_migrations'))
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.nombre);
        IF web_ok THEN
            EXECUTE format('GRANT SELECT ON public.%I TO agroia_web', t.nombre);
            EXECUTE format('DROP POLICY IF EXISTS web_lectura ON public.%I', t.nombre);
            EXECUTE format('CREATE POLICY web_lectura ON public.%I FOR SELECT TO agroia_web USING (true)', t.nombre);
        END IF;
    END LOOP;

    IF web_ok THEN
        FOR v IN
            SELECT c.relname AS nombre
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'v' AND c.relname LIKE 'v\_%'
        LOOP
            EXECUTE format('GRANT SELECT ON public.%I TO agroia_web', v.nombre);
        END LOOP;

        -- Unica escritura permitida a la web: memoria y contadores del asistente.
        FOR t IN SELECT unnest(ARRAY['chat_rate', 'chat_session', 'chat_message']) AS nombre LOOP
            EXECUTE format('GRANT INSERT, UPDATE, DELETE ON public.%I TO agroia_web', t.nombre);
            EXECUTE format('DROP POLICY IF EXISTS web_escritura ON public.%I', t.nombre);
            EXECUTE format('CREATE POLICY web_escritura ON public.%I FOR ALL TO agroia_web USING (true) WITH CHECK (true)', t.nombre);
        END LOOP;
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE public.chat_message_id_seq TO agroia_web';
    END IF;
END
$seguridad$;
