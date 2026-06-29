# ==========================================
# ventasNeira.py
# Sistema de Inventario y Ventas - Neira Store
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import hashlib
import time

# --- CONFIGURACIÓN DE CONEXIÓN GLOBAL ---
DB_URL = st.secrets["DB_URL"]

def conectar_db():
    return psycopg2.connect(DB_URL)

def inicializar_tablas():
    conn = conectar_db()
    conn.autocommit = True
    cur = conn.cursor()
    
    # 1. Tabla de Productos
    cur.execute('''CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY, 
        codigo TEXT UNIQUE NOT NULL, 
        nombre TEXT NOT NULL, 
        categoria TEXT, 
        precio_compra NUMERIC DEFAULT 0.0, 
        precio_venta NUMERIC DEFAULT 0.0, 
        stock_actual INTEGER DEFAULT 0, 
        stock_minimo INTEGER DEFAULT 5,
        proveedor TEXT,
        ubicacion TEXT,
        fecha_registro DATE DEFAULT CURRENT_DATE
    )''')
    
    # 2. Tabla de Ventas
    cur.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY, 
        producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, 
        precio_unitario NUMERIC, 
        total_venta NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, 
        metodo_pago TEXT DEFAULT 'Efectivo',
        cliente TEXT,
        vendedor TEXT,
        estado TEXT DEFAULT 'Completada',
        factura TEXT,
        observaciones TEXT
    )''')
    
    # 3. Tabla de Compras (Entradas de inventario)
    cur.execute('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, 
        producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, 
        costo_unitario NUMERIC, 
        total_compra NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, 
        proveedor TEXT,
        factura_compra TEXT,
        estado TEXT DEFAULT 'Recibida',
        observaciones TEXT
    )''')
    
    # 4. Tabla de Usuarios
    cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, 
        nombre TEXT, 
        usuario TEXT UNIQUE, 
        clave TEXT, 
        rol TEXT DEFAULT 'vendedor'
    )''')
    
    # 5. Tabla de Configuración
    cur.execute('''CREATE TABLE IF NOT EXISTS configuracion (
        id SERIAL PRIMARY KEY, 
        nombre_negocio TEXT DEFAULT 'Neira Store',
        direccion TEXT,
        telefono TEXT,
        email TEXT,
        iva NUMERIC DEFAULT 0.0,
        moneda TEXT DEFAULT '€'
    )''')
    
    # 6. Tabla de Categorías
    cur.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY, 
        nombre TEXT UNIQUE NOT NULL
    )''')
    
    # --- DATOS INICIALES ---
    
    # Insertar usuario admin por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Administrador', 'admin', 'admin2026', 'admin') ON CONFLICT DO NOTHING")
    
    # Insertar usuario vendedor por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Vendedor', 'vendedor', 'vende2026', 'vendedor') ON CONFLICT DO NOTHING")
    
    # Insertar configuración inicial
    cur.execute("INSERT INTO configuracion (id, nombre_negocio, moneda) VALUES (1, 'Neira Store', '€') ON CONFLICT (id) DO NOTHING")
    
    # Insertar categorías base
    categorias_base = ["Electrónica", "Ropa", "Alimentos", "Hogar", "Juguetes", "Herramientas", "Libros", "Deportes"]
    for cat in categorias_base:
        cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
    
    # Añadir columnas adicionales si no existen
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN stock_minimo INTEGER DEFAULT 5")
    except Exception:
        pass
    
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN proveedor TEXT")
    except Exception:
        pass
        
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN ubicacion TEXT")
    except Exception:
        pass
    
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN cliente TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN vendedor TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN factura TEXT")
    except Exception:
        pass
        
    conn.close()

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="Neira Store - Inventario", layout="wide", page_icon="🏪")

# --- CONTROL DE VENTANAS / SESIONES ---
if 'sesion_activa' not in st.session_state:
    st.session_state['sesion_activa'] = True
elif not st.session_state.get('sesion_activa', False):
    st.error("⚠️ Ya hay una ventana o sesión abierta. Cierre las ventanas repetidas para evitar conflictos.")
    st.stop()

# --- SISTEMA ANTI-ATASCOS ---
if 'db_ready' not in st.session_state:
    try:
        inicializar_tablas()
        st.session_state['db_ready'] = True
    except Exception as e:
        st.error(f"Error conectando a la base de datos. Detalle: {e}")
        st.stop()

# --- LOGIN ---
if 'u_rol' not in st.session_state:
    st.session_state['u_rol'] = None
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.sidebar.title("🔐 Acceso al Sistema")
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Ingresar"):
        try:
            conn = conectar_db()
            cur = conn.cursor()
            cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", (u, p))
            resultado = cur.fetchone()
            
            if resultado:
                st.session_state['logged_in'] = True
                st.session_state['u_rol'] = resultado[0]
                conn.close()
                st.rerun()
            else:
                cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", 
                           (u, hashlib.sha256(p.encode()).hexdigest()))
                res_cifrado = cur.fetchone()
                if res_cifrado:
                    st.session_state['logged_in'] = True
                    st.session_state['u_rol'] = res_cifrado[0]
                    conn.close()
                    st.rerun()
                else:
                    st.sidebar.error("Usuario o contraseña incorrectos")
                    conn.close()
        except Exception as e:
            st.sidebar.error(f"Error de conexión: {e}")
    
    st.title("🏪 Sistema de Inventario y Ventas - Neira Store")
    st.info("👋 Bienvenido. Ingrese sus credenciales en la barra lateral.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Productos", "0")
    with col2:
        st.metric("Ventas Hoy", "€0")
    with col3:
        st.metric("Stock Bajo", "0")
    
    st.stop()

# --- MENÚ Y BOTÓN DE CERRAR ---
st.sidebar.title("🏪 Panel de Control")

# Obtener nombre del negocio
try:
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("SELECT nombre_negocio FROM configuracion WHERE id = 1")
    nombre_neg = cur.fetchone()
    negocio_nombre = nombre_neg[0] if nombre_neg else "Neira Store"
    conn.close()
except:
    negocio_nombre = "Neira Store"

st.sidebar.markdown(f"### 🏪 {negocio_nombre}")

# Menú según rol
opciones_menu = [
    "🏠 Inicio",
    "📦 Productos",
    "📥 Compras (Entradas)",
    "💳 Ventas (Salidas)",
    "📊 Balance General"
]

if st.session_state.u_rol == "admin":
    opciones_menu.extend(["🏷️ Categorías", "👥 Usuarios", "⚙️ Configuración"])

menu = st.sidebar.radio("Navegación", opciones_menu)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, type="primary"):
    st.session_state['logged_in'] = False
    st.session_state['u_rol'] = None
    st.rerun()

# ==========================================
# 🏠 INICIO - Dashboard
# ==========================================
if menu == "🏠 Inicio":
    st.subheader("📊 Dashboard General")
    conn = conectar_db()
    
    total_productos = pd.read_sql("SELECT COUNT(*) FROM productos", conn).iloc[0,0]
    stock_total = pd.read_sql("SELECT SUM(stock_actual) FROM productos", conn).iloc[0,0] or 0
    ventas_total = pd.read_sql("SELECT SUM(total_venta) FROM ventas", conn).iloc[0,0] or 0
    
    hoy = datetime.now().date()
    ventas_hoy = pd.read_sql("SELECT SUM(total_venta) FROM ventas WHERE fecha = %s", conn, params=(hoy,)).iloc[0,0] or 0
    stock_bajo = pd.read_sql("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo", conn).iloc[0,0] or 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_productos)
    c2.metric("💰 Ventas Totales", f"{ventas_total:,.2f} €")
    c3.metric("📈 Ventas Hoy", f"{ventas_hoy:,.2f} €")
    c4.metric("⚠️ Stock Bajo", stock_bajo, delta="Revisar" if stock_bajo > 0 else "OK")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Ventas por Producto (Top 5)")
        top_productos = pd.read_sql("""
            SELECT p.nombre, SUM(v.cantidad) as total_vendido
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            GROUP BY p.nombre
            ORDER BY total_vendido DESC
            LIMIT 5
        """, conn)
        if not top_productos.empty:
            st.bar_chart(data=top_productos.set_index('nombre'))
        else:
            st.info("No hay datos de ventas aún.")
    
    with col2:
        st.subheader("📈 Ventas por Categoría")
        ventas_categoria = pd.read_sql("""
            SELECT p.categoria, SUM(v.total_venta) as total
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            GROUP BY p.categoria
            ORDER BY total DESC
        """, conn)
        if not ventas_categoria.empty:
            st.dataframe(ventas_categoria, use_container_width=True)
        else:
            st.info("No hay datos de ventas aún.")
    
    if stock_bajo > 0:
        st.markdown("---")
        st.warning(f"⚠️ {stock_bajo} producto(s) con stock bajo:")
        productos_bajo = pd.read_sql("""
            SELECT nombre, stock_actual, stock_minimo
            FROM productos
            WHERE stock_actual <= stock_minimo
            ORDER BY stock_actual ASC
        """, conn)
        st.dataframe(productos_bajo, use_container_width=True)
    
    conn.close()

# ==========================================
# 📦 PRODUCTOS
# ==========================================
elif menu == "📦 Productos":
    tabs = st.tabs(["➕ Nuevo Producto", "✏️ Editar Producto", "🔍 Ver Productos"])
    
    conn = conectar_db()
    categorias_df = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)
    categorias_lista = categorias_df['nombre'].tolist() if not categorias_df.empty else []
    
    with tabs[0]:
        with st.form("form_nuevo_producto"):
            st.subheader("Registrar Nuevo Producto")
            c1, c2 = st.columns(2)
            
            with c1:
                codigo = st.text_input("Código del Producto *", placeholder="Ej: PROD-001")
                nombre = st.text_input("Nombre del Producto *")
                categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."])
                if categoria == "Nueva...":
                    categoria_nueva = st.text_input("Nombre de nueva categoría")
                    categoria_final = categoria_nueva if categoria_nueva else "Sin categoría"
                else:
                    categoria_final = categoria
            
            with c2:
                precio_compra = st.number_input("Precio de Compra (€)", min_value=0.0, step=0.01)
                precio_venta = st.number_input("Precio de Venta (€)", min_value=0.0, step=0.01)
                stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
                stock_minimo = st.number_input("Stock Mínimo de Alerta", min_value=0, value=5, step=1)
            
            proveedor = st.text_input("Proveedor")
            ubicacion = st.text_input("Ubicación en Almacén")
            
            st.caption("* Campos obligatorios")
            
            if st.form_submit_button("💾 Guardar Producto", type="primary"):
                if not codigo.strip():
                    st.error("⚠️ El código del producto es obligatorio.")
                elif not nombre.strip():
                    st.error("⚠️ El nombre del producto es obligatorio.")
                else:
                    try:
                        cur = conn.cursor()
                        cat_final = categoria_final if categoria_final != "Nueva..." else "Sin categoría"
                        
                        cur.execute("""
                            INSERT INTO productos 
                            (codigo, nombre, categoria, precio_compra, precio_venta, 
                             stock_actual, stock_minimo, proveedor, ubicacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (codigo.upper().strip(), nombre.strip(), cat_final, 
                              precio_compra, precio_venta, stock_inicial, 
                              stock_minimo, proveedor, ubicacion))
                        
                        if categoria == "Nueva..." and categoria_nueva.strip():
                            try:
                                cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", 
                                            (categoria_nueva.strip(),))
                            except:
                                pass
                        
                        conn.commit()
                        st.success("✅ Producto registrado exitosamente")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        if "codigo" in str(e).lower():
                            st.error(f"⚠️ El código '{codigo}' ya está registrado.")
                        else:
                            st.error(f"⚠️ Error: {e}")
    
    with tabs[1]:
        productos_df = pd.read_sql("SELECT id, codigo, nombre FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            producto_seleccionado = st.selectbox(
                "Seleccionar Producto a Editar", 
                productos_df['codigo'] + " - " + productos_df['nombre']
            )
            
            if producto_seleccionado:
                codigo_producto = producto_seleccionado.split(" - ")[0]
                producto_data = pd.read_sql(
                    "SELECT * FROM productos WHERE codigo = %s", 
                    conn, 
                    params=(codigo_producto,)
                ).iloc[0]
                
                with st.form("form_editar_producto"):
                    st.subheader(f"Editando: {producto_data['nombre']}")
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        n_nombre = st.text_input("Nombre", value=producto_data['nombre'])
                        n_categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."], 
                                                  index=categorias_lista.index(producto_data['categoria']) if producto_data['categoria'] in categorias_lista else 0)
                        if n_categoria == "Nueva...":
                            n_categoria_nueva = st.text_input("Nombre de nueva categoría")
                            n_categoria_final = n_categoria_nueva if n_categoria_nueva else "Sin categoría"
                        else:
                            n_categoria_final = n_categoria
                    
                    with c2:
                        n_precio_compra = st.number_input("Precio de Compra (€)", value=float(producto_data['precio_compra'] or 0), step=0.01)
                        n_precio_venta = st.number_input("Precio de Venta (€)", value=float(producto_data['precio_venta'] or 0), step=0.01)
                        n_stock_actual = st.number_input("Stock Actual", value=int(producto_data['stock_actual'] or 0), step=1)
                        n_stock_minimo = st.number_input("Stock Mínimo", value=int(producto_data['stock_minimo'] or 5), step=1)
                    
                    n_proveedor = st.text_input("Proveedor", value=producto_data['proveedor'] or "")
                    n_ubicacion = st.text_input("Ubicación", value=producto_data['ubicacion'] or "")
                    
                    if st.form_submit_button("💾 Actualizar Producto"):
                        try:
                            cur = conn.cursor()
                            cat_final = n_categoria_final if n_categoria_final != "Nueva..." else "Sin categoría"
                            
                            cur.execute("""
                                UPDATE productos SET 
                                    nombre = %s, categoria = %s, precio_compra = %s, 
                                    precio_venta = %s, stock_actual = %s, stock_minimo = %s,
                                    proveedor = %s, ubicacion = %s
                                WHERE codigo = %s
                            """, (n_nombre, cat_final, n_precio_compra, n_precio_venta,
                                  n_stock_actual, n_stock_minimo, n_proveedor, n_ubicacion,
                                  codigo_producto))
                            
                            if n_categoria == "Nueva..." and n_categoria_nueva.strip():
                                try:
                                    cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", 
                                               (n_categoria_nueva.strip(),))
                                except:
                                    pass
                            
                            conn.commit()
                            st.success("✅ Producto actualizado")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"⚠️ Error: {e}")
        else:
            st.info("No hay productos registrados para editar.")
    
    with tabs[2]:
        st.subheader("📋 Inventario Actual")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            categoria_filtro = st.selectbox("Filtrar por Categoría", ["Todas"] + categorias_lista)
        with col_f2:
            stock_filtro = st.selectbox("Filtrar por Stock", ["Todos", "Con Stock", "Sin Stock", "Stock Bajo"])
        
        query = "SELECT codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo, proveedor FROM productos"
        condiciones = []
        params = []
        
        if categoria_filtro != "Todas":
            condiciones.append("categoria = %s")
            params.append(categoria_filtro)
        
        if stock_filtro == "Con Stock":
            condiciones.append("stock_actual > 0")
        elif stock_filtro == "Sin Stock":
            condiciones.append("stock_actual = 0")
        elif stock_filtro == "Stock Bajo":
            condiciones.append("stock_actual <= stock_minimo")
        
        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)
        
        query += " ORDER BY nombre"
        
        productos_mostrar = pd.read_sql(query, conn, params=params if params else None)
        
        if not productos_mostrar.empty:
            st.dataframe(productos_mostrar, use_container_width=True)
            
            total_valor = (productos_mostrar['precio_compra'] * productos_mostrar['stock_actual']).sum()
            total_venta = (productos_mostrar['precio_venta'] * productos_mostrar['stock_actual']).sum()
            
            c1, c2 = st.columns(2)
            c1.metric("💰 Valor de Inventario (Costo)", f"{total_valor:,.2f} €")
            c2.metric("💰 Valor de Inventario (Venta)", f"{total_venta:,.2f} €")
            
            csv_data = productos_mostrar.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Inventario", 
                data=csv_data, 
                file_name=f"inventario_{datetime.now().strftime('%Y%m%d')}.csv", 
                mime="text/csv"
            )
        else:
            st.info("No hay productos que coincidan con los filtros seleccionados.")
    
    conn.close()

# ==========================================
# 📥 COMPRAS (Entradas)
# ==========================================
elif menu == "📥 Compras (Entradas)":
    tabs = st.tabs(["➕ Registrar Compra", "📋 Historial de Compras"])
    
    conn = conectar_db()
    
    with tabs[0]:
        st.subheader("Registrar Entrada de Mercancía (Compra)")
        
        productos_df = pd.read_sql("SELECT id, codigo, nombre, precio_compra FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            with st.form("form_registrar_compra"):
                c1, c2 = st.columns(2)
                
                with c1:
                    producto_sel = st.selectbox("Seleccionar Producto", 
                                               productos_df['codigo'] + " - " + productos_df['nombre'])
                    producto_id = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['id'].values[0]
                    precio_compra_actual = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['precio_compra'].values[0]
                    
                    cantidad = st.number_input("Cantidad Comprada", min_value=1, step=1)
                    costo_unitario = st.number_input("Costo Unitario (€)", min_value=0.0, value=float(precio_compra_actual or 0), step=0.01)
                
                with c2:
                    total_compra = cantidad * costo_unitario
                    st.metric("Total Compra", f"{total_compra:,.2f} €")
                    proveedor = st.text_input("Proveedor")
                    factura_compra = st.text_input("Número de Factura")
                    fecha_compra = st.date_input("Fecha de Compra", datetime.now().date())
                
                observaciones = st.text_area("Observaciones")
                
                st.info(f"📦 Producto: {producto_sel} | Cantidad: {cantidad} | Costo Unitario: {costo_unitario:.2f}€ | Total: {total_compra:.2f}€")
                
                if st.form_submit_button("✅ Registrar Compra", type="primary"):
                    try:
                        cur = conn.cursor()
                        
                        cur.execute("""
                            INSERT INTO compras 
                            (producto_id, cantidad, costo_unitario, total_compra, fecha, 
                             proveedor, factura_compra, observaciones, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Recibida')
                        """, (producto_id, cantidad, costo_unitario, total_compra, 
                              fecha_compra, proveedor, factura_compra, observaciones))
                        
                        cur.execute("""
                            UPDATE productos 
                            SET stock_actual = stock_actual + %s,
                                precio_compra = %s
                            WHERE id = %s
                        """, (cantidad, costo_unitario, producto_id))
                        
                        conn.commit()
                        st.success(f"✅ Compra registrada exitosamente. Stock actualizado +{cantidad} unidades.")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        st.error(f"⚠️ Error al registrar compra: {e}")
        else:
            st.warning("⚠️ No hay productos registrados. Registra productos primero.")
    
    with tabs[1]:
        st.subheader("📋 Historial de Compras")
        
        compras_df = pd.read_sql("""
            SELECT c.*, p.codigo, p.nombre 
            FROM compras c
            JOIN productos p ON c.producto_id = p.id
            ORDER BY c.fecha DESC
        """, conn)
        
        if not compras_df.empty:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_ini = st.date_input("Desde", compras_df['fecha'].min() if not compras_df.empty else datetime.now().date(), key="compras_desde")
            with col_f2:
                fecha_fin = st.date_input("Hasta", compras_df['fecha'].max() if not compras_df.empty else datetime.now().date(), key="compras_hasta")
            
            compras_df['fecha'] = pd.to_datetime(compras_df['fecha']).dt.date
            compras_filtradas = compras_df[
                (compras_df['fecha'] >= fecha_ini) & 
                (compras_df['fecha'] <= fecha_fin)
            ]
            
            if not compras_filtradas.empty:
                total_invertido = compras_filtradas['total_compra'].sum()
                total_unidades = compras_filtradas['cantidad'].sum()
                
                c1, c2 = st.columns(2)
                c1.metric("💰 Total Invertido", f"{total_invertido:,.2f} €")
                c2.metric("📦 Total Unidades Compradas", total_unidades)
                
                st.dataframe(compras_filtradas[['fecha', 'codigo', 'nombre', 'cantidad', 'costo_unitario', 'total_compra', 'proveedor']], 
                           use_container_width=True)
            else:
                st.info("No hay compras en el rango de fechas seleccionado.")
        else:
            st.info("Aún no hay registros de compras.")
    
    conn.close()

# ==========================================
# 💳 VENTAS (Salidas)
# ==========================================
elif menu == "💳 Ventas (Salidas)":
    tabs = st.tabs(["➕ Registrar Venta", "📋 Historial de Ventas"])
    
    conn = conectar_db()
    
    with tabs[0]:
        st.subheader("Registrar Salida de Mercancía (Venta)")
        
        productos_df = pd.read_sql("SELECT id, codigo, nombre, precio_venta, stock_actual FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            with st.form("form_registrar_venta"):
                c1, c2 = st.columns(2)
                
                with c1:
                    producto_sel = st.selectbox("Seleccionar Producto", 
                                               productos_df['codigo'] + " - " + productos_df['nombre'] + " (Stock: " + productos_df['stock_actual'].astype(str) + ")")
                    producto_id = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['id'].values[0]
                    precio_venta_actual = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['precio_venta'].values[0]
                    stock_disponible = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['stock_actual'].values[0]
                    
                    cantidad = st.number_input("Cantidad a Vender", min_value=1, max_value=int(stock_disponible) if stock_disponible > 0 else 1, step=1)
                    precio_unitario = st.number_input("Precio de Venta Unitario (€)", min_value=0.0, value=float(precio_venta_actual or 0), step=0.01)
                
                with c2:
                    total_venta = cantidad * precio_unitario
                    st.metric("Total Venta", f"{total_venta:,.2f} €")
                    metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia", "Bizum"])
                    cliente = st.text_input("Cliente")
                    factura = st.text_input("Número de Factura")
                    fecha_venta = st.date_input("Fecha de Venta", datetime.now().date(), key="ventas_fecha")
                    vendedor = st.text_input("Vendedor", value=st.session_state.get('u_rol', ''))
                
                observaciones = st.text_area("Observaciones")
                
                if cantidad > stock_disponible:
                    st.error(f"⚠️ Stock insuficiente. Disponible: {stock_disponible} unidades.")
                else:
                    st.success(f"✅ Stock disponible: {stock_disponible} unidades. Venta de {cantidad} unidades.")
                    st.info(f"💰 Subtotal: {total_venta:.2f}€")
                
                if st.form_submit_button("✅ Registrar Venta", type="primary"):
                    if cantidad > stock_disponible:
                        st.error("⚠️ No hay suficiente stock para esta venta.")
                    else:
                        try:
                            cur = conn.cursor()
                            
                            cur.execute("""
                                INSERT INTO ventas 
                                (producto_id, cantidad, precio_unitario, total_venta, fecha, 
                                 metodo_pago, cliente, vendedor, factura, observaciones, estado)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Completada')
                            """, (producto_id, cantidad, precio_unitario, total_venta, 
                                  fecha_venta, metodo_pago, cliente, vendedor, factura, observaciones))
                            
                            cur.execute("""
                                UPDATE productos 
                                SET stock_actual = stock_actual - %s
                                WHERE id = %s
                            """, (cantidad, producto_id))
                            
                            conn.commit()
                            st.success(f"✅ Venta registrada exitosamente. Stock actualizado -{cantidad} unidades.")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            conn.rollback()
                            st.error(f"⚠️ Error al registrar venta: {e}")
        else:
            st.warning("⚠️ No hay productos registrados. Registra productos primero.")
    
    with tabs[1]:
        st.subheader("📋 Historial de Ventas")
        
        ventas_df = pd.read_sql("""
            SELECT v.*, p.codigo, p.nombre 
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            ORDER BY v.fecha DESC
        """, conn)
        
        if not ventas_df.empty:
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                fecha_ini = st.date_input("Desde", ventas_df['fecha'].min() if not ventas_df.empty else datetime.now().date(), key="hist_ventas_desde")
            with col_f2:
                fecha_fin = st.date_input("Hasta", ventas_df['fecha'].max() if not ventas_df.empty else datetime.now().date(), key="hist_ventas_hasta")
            with col_f3:
                metodo_filtro = st.selectbox("Método de Pago", ["Todos"] + ventas_df['metodo_pago'].unique().tolist())
            
            ventas_df['fecha'] = pd.to_datetime(ventas_df['fecha']).dt.date
            ventas_filtradas = ventas_df[
                (ventas_df['fecha'] >= fecha_ini) & 
                (ventas_df['fecha'] <= fecha_fin)
            ]
            
            if metodo_filtro != "Todos":
                ventas_filtradas = ventas_filtradas[ventas_filtradas['metodo_pago'] == metodo_filtro]
            
            if not ventas_filtradas.empty:
                total_ventas = ventas_filtradas['total_venta'].sum()
                total_unidades = ventas_filtradas['cantidad'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Total Ventas", f"{total_ventas:,.2f} €")
                c2.metric("📦 Total Unidades Vendidas", total_unidades)
                c3.metric("📊 Promedio por Venta", f"{(total_ventas/len(ventas_filtradas)):.2f} €" if len(ventas_filtradas) > 0 else "0 €")
                
                st.subheader("📈 Ventas Diarias")
                ventas_diarias = ventas_filtradas.groupby('fecha')['total_venta'].sum().reset_index()
                st.line_chart(data=ventas_diarias.set_index('fecha'))
                
                st.dataframe(ventas_filtradas[['fecha', 'codigo', 'nombre', 'cantidad', 'precio_unitario', 'total_venta', 'metodo_pago', 'cliente']], 
                           use_container_width=True)
                
                csv_data = ventas_filtradas.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Reporte de Ventas", 
                    data=csv_data, 
                    file_name=f"ventas_{fecha_ini}_a_{fecha_fin}.csv", 
                    mime="text/csv"
                )
            else:
                st.info("No hay ventas en el rango de fechas seleccionado.")
        else:
            st.info("Aún no hay registros de ventas.")
    
    conn.close()

# ==========================================
# 📊 BALANCE GENERAL
# ==========================================
elif menu == "📊 Balance General":
    st.subheader("📊 Balance General del Negocio")
    
    conn = conectar_db()
    
    st.markdown("### 📦 Resumen de Inventario")
    
    inventario_df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_actual) as total_unidades,
            SUM(stock_actual * precio_compra) as valor_inventario_costo,
            SUM(stock_actual * precio_venta) as valor_inventario_venta
        FROM productos
    """, conn)
    
    if not inventario_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        total_prod = inventario_df['total_productos'].iloc[0] or 0
        total_unid = inventario_df['total_unidades'].iloc[0] or 0
        valor_costo = inventario_df['valor_inventario_costo'].iloc[0] or 0.0
        valor_venta = inventario_df['valor_inventario_venta'].iloc[0] or 0.0
        ganancia_esperada = valor_venta - valor_costo
        
        col1.metric("📦 Total Productos", total_prod)
        col2.metric("🔢 Unidades Totales", int(total_unid))
        col3.metric("💶 Inversión (Costo)", f"{valor_costo:,.2f} €")
        col4.metric("📈 Ganancia Proyectada", f"{ganancia_esperada:,.2f} €")
        
        st.markdown("---")
        
        st.subheader("📋 Resumen de Transacciones")
        
        flujo_df = pd.read_sql("""
            SELECT 
                (SELECT COALESCE(SUM(total_venta), 0) FROM ventas) as total_ingresos,
                (SELECT COALESCE(SUM(total_compra), 0) FROM compras) as total_egresos
        """, conn)
        
        ingresos = flujo_df['total_ingresos'].iloc[0]
        egresos = flujo_df['total_egresos'].iloc[0]
        balance_actual = ingresos - egresos
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos (Ventas)", f"{ingresos:,.2f} €")
        c2.metric("Egresos (Compras)", f"{egresos:,.2f} €")
        c3.metric("Balance Neto", f"{balance_actual:,.2f} €", delta=float(balance_actual))

    conn.close()
