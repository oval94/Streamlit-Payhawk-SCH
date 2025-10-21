# app.py
import streamlit as st

# Título de la aplicación
st.title('💪 Calculadora de Índice de Masa Corporal (IMC)')

# Encabezado
st.header('Bienvenido/a a la calculadora de IMC')
st.write('Por favor, introduce tus datos en la barra lateral.')

# Barra lateral para la entrada de datos
st.sidebar.header('Tus Datos')
peso = st.sidebar.number_input('Peso (en kg)', min_value=1.0, value=70.0, step=0.5)
altura = st.sidebar.number_input('Altura (en metros)', min_value=0.1, value=1.75, step=0.01)

# Botón para calcular
if st.sidebar.button('Calcular IMC'):
    st.write(f"Tu peso es {peso} kg y tu altura es {altura} m.")
    st.success("¡Cálculo iniciado! (Lógica pendiente)")