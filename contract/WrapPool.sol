// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "./WrapSell.sol";

/**
 * @title WrapPool
 * @dev Stablecoin backed by multiple WrapSell contracts as collateral
 * Each WrapSell represents a specific card type with multiple card units as collateral
 */
contract WrapPool is ERC20, Ownable {
    // Mapping of WrapSell contracts that serve as collateral
    mapping(address => bool) public acceptedWrapSells;
    mapping(address => uint256) public wrapSellWeights; // Weight/value multiplier for each WrapSell
    address[] public wrapSellList;

    // Pool configuration
    uint256 public collateralizationRatio = 150; // 150% minimum collateralization
    uint256 public constant PRECISION = 1e18;

    // Events
    event WrapSellAdded(address indexed wrapSell, uint256 weight);
    event WrapSellRemoved(address indexed wrapSell);
    event StablecoinMinted(
        address indexed user,
        uint256 amount,
        uint256 collateralValue
    );
    event StablecoinBurned(address indexed user, uint256 amount);
    event CollateralizationRatioUpdated(uint256 newRatio);

    constructor(
        string memory name,
        string memory symbol
    ) ERC20(name, symbol) Ownable(msg.sender) {}

    /**
     * @dev Add a WrapSell contract as accepted collateral
     * @param wrapSell Address of the WrapSell contract
     * @param weight Weight/value multiplier for this WrapSell (scaled by 1e18)
     */
    function addWrapSell(address wrapSell, uint256 weight) external onlyOwner {
        require(wrapSell != address(0), "Invalid WrapSell address");
        require(weight > 0, "Weight must be greater than 0");
        require(!acceptedWrapSells[wrapSell], "WrapSell already added");

        acceptedWrapSells[wrapSell] = true;
        wrapSellWeights[wrapSell] = weight;
        wrapSellList.push(wrapSell);

        emit WrapSellAdded(wrapSell, weight);
    }

    /**
     * @dev Remove a WrapSell contract from accepted collateral
     * @param wrapSell Address of the WrapSell contract to remove
     */
    function removeWrapSell(address wrapSell) external onlyOwner {
        require(acceptedWrapSells[wrapSell], "WrapSell not found");

        acceptedWrapSells[wrapSell] = false;
        wrapSellWeights[wrapSell] = 0;

        // Remove from array
        for (uint256 i = 0; i < wrapSellList.length; i++) {
            if (wrapSellList[i] == wrapSell) {
                wrapSellList[i] = wrapSellList[wrapSellList.length - 1];
                wrapSellList.pop();
                break;
            }
        }

        emit WrapSellRemoved(wrapSell);
    }

    /**
     * @dev Calculate total collateral value from all WrapSell contracts
     * @return Total collateral value in wei
     */
    function getTotalCollateralValue() public view returns (uint256) {
        uint256 totalValue = 0;

        for (uint256 i = 0; i < wrapSellList.length; i++) {
            address wrapSell = wrapSellList[i];
            if (acceptedWrapSells[wrapSell]) {
                WrapSell wrapSellContract = WrapSell(wrapSell);
                uint256 wrapSellValue = wrapSellContract
                    .getTotalCollateralValue();
                uint256 weight = wrapSellWeights[wrapSell];

                totalValue += (wrapSellValue * weight) / PRECISION;
            }
        }

        return totalValue;
    }

    /**
     * @dev Calculate current collateralization ratio
     * @return Collateralization ratio as percentage (150 = 150%)
     */
    function getCurrentCollateralizationRatio() public view returns (uint256) {
        uint256 totalSupply_ = totalSupply();
        if (totalSupply_ == 0) return type(uint256).max;

        uint256 collateralValue = getTotalCollateralValue();
        return (collateralValue * 100) / totalSupply_;
    }

    /**
     * @dev Mint stablecoins based on available collateral
     * @param amount Amount of stablecoins to mint
     */
    function mint(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");

        uint256 collateralValue = getTotalCollateralValue();
        uint256 newTotalSupply = totalSupply() + amount;
        uint256 newCollateralizationRatio = (collateralValue * 100) /
            newTotalSupply;

        require(
            newCollateralizationRatio >= collateralizationRatio,
            "Insufficient collateralization"
        );

        _mint(msg.sender, amount);
        emit StablecoinMinted(msg.sender, amount, collateralValue);
    }

    /**
     * @dev Burn stablecoins
     * @param amount Amount of stablecoins to burn
     */
    function burn(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");
        require(balanceOf(msg.sender) >= amount, "Insufficient balance");

        _burn(msg.sender, amount);
        emit StablecoinBurned(msg.sender, amount);
    }

    /**
     * @dev Update minimum collateralization ratio (only owner)
     * @param newRatio New collateralization ratio (150 = 150%)
     */
    function setCollateralizationRatio(uint256 newRatio) external onlyOwner {
        require(newRatio >= 100, "Ratio must be at least 100%");
        collateralizationRatio = newRatio;
        emit CollateralizationRatioUpdated(newRatio);
    }

    /**
     * @dev Update weight for a WrapSell contract
     * @param wrapSell Address of the WrapSell contract
     * @param newWeight New weight value
     */
    function updateWrapSellWeight(
        address wrapSell,
        uint256 newWeight
    ) external onlyOwner {
        require(acceptedWrapSells[wrapSell], "WrapSell not accepted");
        require(newWeight > 0, "Weight must be greater than 0");

        wrapSellWeights[wrapSell] = newWeight;
    }

    /**
     * @dev Get list of all accepted WrapSell contracts
     * @return Array of WrapSell contract addresses
     */
    function getAcceptedWrapSells() external view returns (address[] memory) {
        return wrapSellList;
    }

    /**
     * @dev Get detailed pool information
     * @return poolValue Total collateral value
     * @return stablecoinSupply Total stablecoin supply
     * @return collateralizationRatio_ Current collateralization ratio
     * @return wrapSellCount Number of accepted WrapSell contracts
     */
    function getPoolInfo()
        external
        view
        returns (
            uint256 poolValue,
            uint256 stablecoinSupply,
            uint256 collateralizationRatio_,
            uint256 wrapSellCount
        )
    {
        poolValue = getTotalCollateralValue();
        stablecoinSupply = totalSupply();
        collateralizationRatio_ = getCurrentCollateralizationRatio();
        wrapSellCount = wrapSellList.length;
    }

    /**
     * @dev Emergency function to pause minting if collateralization falls below safe levels
     */
    function isHealthy() public view returns (bool) {
        return getCurrentCollateralizationRatio() >= collateralizationRatio;
    }
}
