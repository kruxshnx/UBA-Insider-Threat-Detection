import React, { createContext, useState, useContext, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
    const [lowPowerMode, setLowPowerMode] = useState(false);

    useEffect(() => {
        if (lowPowerMode) {
            document.body.classList.add('low-power-mode');
        } else {
            document.body.classList.remove('low-power-mode');
        }
    }, [lowPowerMode]);

    const toggleLowPowerMode = () => {
        setLowPowerMode(prev => !prev);
    };

    return (
        <ThemeContext.Provider value={{ lowPowerMode, toggleLowPowerMode }}>
            {children}
        </ThemeContext.Provider>
    );
};
