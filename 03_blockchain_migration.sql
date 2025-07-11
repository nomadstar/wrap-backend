-- Agregar columnas para tracking de blockchain deployment
-- Solo agrega las columnas si no existen

-- Para wrap_pools
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_pools' AND column_name='transaction_hash') THEN
        ALTER TABLE wrap_pools ADD COLUMN transaction_hash VARCHAR(66);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_pools' AND column_name='block_number') THEN
        ALTER TABLE wrap_pools ADD COLUMN block_number BIGINT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_pools' AND column_name='gas_used') THEN
        ALTER TABLE wrap_pools ADD COLUMN gas_used BIGINT;
    END IF;
END $$;

-- Para wrap_sells
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_sells' AND column_name='transaction_hash') THEN
        ALTER TABLE wrap_sells ADD COLUMN transaction_hash VARCHAR(66);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_sells' AND column_name='block_number') THEN
        ALTER TABLE wrap_sells ADD COLUMN block_number BIGINT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wrap_sells' AND column_name='gas_used') THEN
        ALTER TABLE wrap_sells ADD COLUMN gas_used BIGINT;
    END IF;
END $$;
