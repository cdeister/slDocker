########################################################################
########################################################################
########################################################################
####																####
####    slAIDevel v0.25												####
####																####
####    The development module for testing new AI/Data Science		####
####    features/extensions for Stocklabs.							####
####    This is a Python program with a REACT interface using       ####
####	DASH and DASH-Bootstrap Components							####
#### 																####
####    questions about this code:									####
####			--> Chris Deister - cdeister@brown.edu 				####
#### 																####
####    Stocklabs is: TheFly w/Tr3yWay (Eddy) 						####
####																####
########################################################################
########################################################################
########################################################################

# useage: Currently, 0.25 allows:
#	0) It's limited. I have not added all the Python code we have yet. UI programing with new library == learning curve.
#	1) you to input a StockLabs API
#	2) make groupings of stock tickers, by entering a name in entry and clicking add.
#	3) you can select groups
#	4) you can manually add a ticker to each group
#	5) you can remove tickers from a group
#	6) you can add tickers from a StockLabs portfolio by entring its id#
#	7) you can grab a pre-specified amount of 1min data, more flexibility pending Deister API education and/or API tweaks
#	8) you can plot a correlation matrix of the data's avg price entries.
#	9) you can click "Get Tech" to compute core tech score components (todo: working on sub rosa now)
#	10) There is a default group "macroDefault" you must select this and compute its tech components first, if you want beta to be calculated.
#	11) Tech Components for macroDefualt also needed for sub rosa. 
#	12) Added Score Tech button, this scores the Tech Components.
#	13) Subrosas mostly work. The only limitation ATM is consistently feeding the discounting funciton industry IDs.
#	14) All tech score components can be plotted.
#	15) Plot on any of two graph/matrix rows.
#
# current known bugs:
#	1) Ticker drop-down will not show you a placeholder if you add to a fresh group's tickers.
#	1b) Basically the only thing that will display in the ticker drop down is whatever you select for the selected group.
#	1c) if you want to inspect single ticker data you have to select one
#	1c) There is a reason for this, when I am the only one to have debuged ui code like this, I leave out a degree of freedom ahead of time in order to have room to fix other bugs.
#	2) You need to wait a bit after you click get data. You should see the number change below, but it will say updating in your browser's status bar. 
#		(todo: will add feedback/progress)
#	2a) I added a wait period in between API calls so not to throttle any limits that may exist.
#	3) Biggest one: Everything writes to a big pandas array, but, if you double score etc. it appends, does not replace.
#	3a) This gets fixed either 0.25 or 0.3 


###############################
######	Dependencies	#######
###############################

import pandas as pd
import numpy as np
import dash
from dash import html
from dash import dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
import plotly.express as px
import plotly.graph_objects as go
import os
import requests
import json
import time
import datetime

#########################################
######## Initialize Dash/REACT	#########
#########################################

app = dash.Dash(external_stylesheets=[dbc.themes.SLATE])

load_figure_template("slate")
server = app.server
# sl banner https://app.stocklabs.com/img/logo.svg

################################
######## SL: Functions #########
################################

def thresholdByQunatiles(data):
	quarts=np.quantile(data,[0.25,0.5,0.75])

	# determine the ratio of upside to downside
	# this is probably a good threshold adjustment
	btmP=quarts[1]-quarts[0]
	topP=quarts[2]-quarts[1]

	if btmP != 0:
		upDwnBias=topP/btmP
	else:
		upDwnBias=0

	thrAdjust=abs(1.5-upDwnBias)
	iqrTh=1.5+thrAdjust

	dIQR=quarts[2]-quarts[0]

	topFence=quarts[2]+(1.5*dIQR)
	bottomFence=quarts[2]-(1.5*dIQR)

	adjTopFence=quarts[2]+(iqrTh*dIQR)
	adjBottomFence=quarts[0]-(iqrTh*dIQR)

	anUpEvs=np.where(data>=adjTopFence)[0]
	anDwnEvs=np.where(data<=adjBottomFence)[0]
	return anUpEvs,anDwnEvs

def getTickerDataFromSL(ticker,apiKey):
	response = requests.get('https://api.stocklabs.com/chart_ticks?symbol={}&type=symbol&resolution=1&from=1m&api_key='.format(ticker) + '{}'.format(apiKey))
	aa=response.json()['data']['bars']

	# aa[0].keys()
	t_times=[]

	pr_op=[]
	pr_hg=[]
	pr_lw=[]
	pr_cl=[]
	pr_avg=[]
	pr_ad=[]

	t_volume=[]

	for i in np.arange(0,len(aa)):
		tTime=pd.Timestamp(int(aa[i]['time']/1000), unit='s', tz='US/Eastern')
		t_times.append(tTime)
		pr_op.append(aa[i]['open'])
		pr_hg.append(aa[i]['high'])
		pr_lw.append(aa[i]['low'])
		pr_cl.append(aa[i]['close'])
		pr_avg.append(np.mean([aa[i]['high'],aa[i]['low']]))
		tHSpr=(aa[i]['high']-aa[i]['close'])
		tRSpr=(aa[i]['high']-aa[i]['low'])
		if tRSpr>0:
			pr_ad.append(1-(tHSpr/tRSpr))
		else:
			pr_ad.append(0)
		t_volume.append(aa[i]['volume'])

	tickerData=pd.DataFrame([pr_op,pr_hg,pr_lw,pr_cl,pr_avg,pr_ad,t_volume]).T
	tickerData=tickerData.set_index([t_times])
	exec('tickerData.columns = ["{}","{}","{}","{}","{}","{}","{}"]'.format('{}_open'.format(ticker),'{}_high'.format(ticker),'{}_low'.format(ticker),'{}_close'.format(ticker),'{}_avg'.format(ticker),'{}_ad'.format(ticker),'{}_volume'.format(ticker)))
	return tickerData

def getTickersFromPortfolio(portID,apiKey):
	nonKeyURL='https://api.stocklabs.com/portfolio_positions?id={}&api_key='.format(portID)
	response = requests.get(nonKeyURL + '{}'.format(apiKey))
	pTickers=[]
	aa=response.json()['data']
	for i in np.arange(0,len(aa)):
		pTickers.append(aa[i]['symbol']['symbol'])
	return pTickers
	
def combineAndFixTickerData(data1,data2):
	#todo: this should error check and return original NaNs
	combinedD=pd.concat([data1,data2], axis=1)
	combinedD=combinedD.fillna(method='ffill')
	return combinedD

def addProcedureToTickerList(tickerList,procString):
	# this will filter the frame looking for avg in all
	procTickers=[]
	for i in np.arange(0,len(tickerList)):
		procTickers.append('{}{}'.format(tickerList[i],procString))
		
	return procTickers

def addTickersToGroup(newTickerString,curTickerStrings,curTickerData,apiKey):
	
	# if you need to add an index to a group you made (don't fetch data you already have)
	curTickerStrings = curTickerStrings + [newTickerString]
	addTicker=getTickerDataFromSL(newTickerString,apiKey)
	curTickerData=combineAndFixTickerData(curTickerData,addTicker)
	addTicker=[]
	return curTickerStrings, curTickerData

def calculateTechMetrics(dataDict,inputGrp,binWidth):
	print(np.shape(currentData))
	print('metric debug:{}'.format(inputGrp))

	# often the macroData set may not match dimensions of dataSet from group
	macroData = dataDict['macroDefault'][1]
	currentData = dataDict[inputGrp][1]

	currentData = currentData.loc[macroData.index]

	if np.shape(macroData)[0]>np.shape(currentData)[0]:
		macroData=macroData.loc[currentData.index]
	elif np.shape(macroData)[0]<np.shape(currentData)[0]:
		currentData=currentData.loc[macroData.index]
		macroData.fillna(method='ffill')
		macroData.fillna(method='bfill')
		currentData.fillna(method='ffill')
		currentData.fillna(method='bfill')

	print('metric uneven?')
	print(np.shape(macroData))
	print(np.shape(currentData))



	# This will return pandas data suitable to add to the globalDict for the group
	# in your procedures. 

	# get pandas strings for components for all symbols in our group
	cTickers = dataDict[inputGrp][0]
	print(cTickers)
	avgPriceStrs = addProcedureToTickerList(cTickers,'_avg')
	volumeeStrs = addProcedureToTickerList(cTickers,'_volume')
	adStrs = addProcedureToTickerList(cTickers,'_ad')

	# we start with a binned version of prices and volume
	# pad the first binWidth-1 samples with sample at binWidth (no Nans)
	# todo: consider rolling mean for first bin, or yesterday close

	avgPrices=currentData[avgPriceStrs].rolling(binWidth).mean()
	avgPrices.iloc[0:binWidth-1]=avgPrices.iloc[binWidth]
	avgVolume=currentData[volumeeStrs].rolling(binWidth).mean()
	avgVolume.iloc[0:binWidth-1]=avgVolume.iloc[binWidth]

	#get price performance, avgPrices is ahead of incoming data by a binWidth
	techmetric_price = currentData[avgPriceStrs].div(avgPrices).sub(1)
	techmetric_volDelta = currentData[volumeeStrs].div(avgVolume).sub(1)
	# make the columns nice
	

	#now calculate RSI (pandas .where is reversed)
	rs_gains=techmetric_price.where(techmetric_price > 0, 0, inplace=False).div(binWidth).mul(100)
	rs_loses=techmetric_price.where(techmetric_price <= 0, 0, inplace=False).abs().div(binWidth).mul(100)
	rs_RS=rs_gains.div(rs_loses.add(0.000001))
	techmetric_RSI=(100-(100/(rs_RS.add(1))))
	techmetric_smRSI=techmetric_RSI.ewm(binWidth).mean().rolling(binWidth,win_type='gaussian').mean(std=binWidth)
	techmetric_smRSI.iloc[0:binWidth-1]=techmetric_smRSI.iloc[binWidth]

	# # todo: beta! we need market vector to be consistent per group



	# accum/dist
	techmetric_accDist=currentData[adStrs].rolling(binWidth).mean()
	techmetric_accDist.iloc[0:binWidth-1]=techmetric_accDist.iloc[binWidth]

	
	# final versions, nice columns
	techmetric_price.columns = addProcedureToTickerList(cTickers,'_pp')
	techmetric_volDelta.columns = addProcedureToTickerList(cTickers,'_vd')
	techmetric_RSI.columns = addProcedureToTickerList(cTickers,'_rsi')
	techmetric_smRSI.columns = addProcedureToTickerList(cTickers,'_rsiSmooth')
	techmetric_accDist.columns = addProcedureToTickerList(cTickers,'_adSmooth')
	finDF=pd.concat([techmetric_price, techmetric_volDelta], axis=1)
	finDF=pd.concat([finDF, techmetric_RSI], axis=1)
	finDF=pd.concat([finDF, techmetric_smRSI], axis=1)
	finDF=pd.concat([finDF, techmetric_accDist], axis=1)
	
	# beta is a special case that need macroDefault to have data already.
	try:


		# macroAvgPriceStrs = addProcedureToTickerList(dataDict['macroDefault'][0],'_avg')
		
		bc1=currentData[avgPriceStrs].rolling(binWidth).mean()
		bc1.iloc[0:binWidth-1]=bc1.iloc[binWidth]
		bc2=macroData['SPY_avg'].rolling(binWidth).mean()
		bc2.iloc[0:binWidth-1]=bc2.iloc[binWidth]


		techmetric_beta=bc1.rolling(binWidth).cov(bc2)
		techmetric_beta.iloc[0:binWidth-1]=techmetric_beta.iloc[binWidth]
		
		techmetric_beta.columns = addProcedureToTickerList(cTickers,'_beta')

		finDF=pd.concat([finDF, techmetric_beta], axis=1)
		

	except:
		print('error: get macro data first, nothing to compute beta')

	# finDF.fillna(method='ffill')
	# finDF.fillna(method='bfill')
	print('metric fin uneven?')
	print(np.shape(macroData))
	print(np.shape(currentData))
	print(np.shape(finDF))
	return finDF

def scoreTechMetrics(dataDict,inpGrp,binWidth):
	# ,subRosa=0
	# This will return pandas data suitable to add to the globalDict for the group
	# in your procedures. 

	# dataDict=dataDict.fillna(method='ffill')
	# dataDict=dataDict.fillna(method='bfill')


	# often the macroData set may not match dimensions of dataSet from group
	macroData = dataDict['macroDefault'][1]
	

	dataDict[inpGrp][1] = dataDict[inpGrp][1].loc[macroData.index]

	print('score debug:{}'.format(inpGrp))

	cTickers = dataDict[inpGrp][0]
	cTypes = dataDict[inpGrp][2]
	print('got these tickers ')
	print(cTickers)
	print(cTypes)

	useETF = 0
	if inpGrp == 'macroDefault':
		print('using ETF')
		useETF = 1


	techmetric_priceStr = addProcedureToTickerList(cTickers,'_pp')
	techmetric_volDeltaStr = addProcedureToTickerList(cTickers,'_vd')
	techmetric_RSIStr = addProcedureToTickerList(cTickers,'_rsi')
	techmetric_smRSIStr = addProcedureToTickerList(cTickers,'_rsiSmooth')
	techmetric_accDistStr = addProcedureToTickerList(cTickers,'_adSmooth')
	techmetric_betaStr = addProcedureToTickerList(cTickers,'_beta')
	print('got through stings ')
	aggStrings = addProcedureToTickerList(cTickers,'_aggTech')
	print('got through stings ')


	pScores=dataDict[inpGrp][1][techmetric_priceStr].copy()
	print('made pscore copy')
	
	if useETF == 1:
		pScores.iloc[dataDict[inpGrp][1][techmetric_priceStr].values<=0.001]=1
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.001) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.05) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.10) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.15)]=5
		print('made pscores')
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')

		print('made pscores cols')
		aggScore = pScores.mul(0.3).values
		print('made agg')
		print(aggScore)
	else:
		pScores.iloc[dataDict[inpGrp][1][techmetric_priceStr].values<=0.01]=1
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.01) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.05) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.10) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.15)]=5
		print('made pscores')
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')

		print('made pscores cols')
		aggScore = pScores.mul(0.3).values




	RSIScores=dataDict[inpGrp][1][techmetric_smRSIStr].copy()
	print('made rsi')
	RSIScores.iloc[dataDict[inpGrp][1][techmetric_smRSIStr].values<=60]=1
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>60) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=80)]=2
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>80) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=90)]=3
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>90) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=95)]=4
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>95)]=5

	RSIScores.columns = addProcedureToTickerList(cTickers,'_rsiSmooth_score')
	print('scored rsi')
	# start cleaning up for memory use etc. 
	finDF=pd.concat([pScores, RSIScores], axis=1)
	print('made df')
	aggScore = aggScore + RSIScores.mul(0.1).values
	print('added to agg')
	pScores=[]
	RSIScores=[]

	ADScores=dataDict[inpGrp][1][techmetric_accDistStr].copy()
	print('copied ad')
	ADScores.iloc[dataDict[inpGrp][1][techmetric_accDistStr].values<=0.50]=1
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.50) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.75)]=2
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.75) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.85)]=3
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.85) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.95)]=4
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.95)]=5
	print('score ad')
	ADScores.columns = addProcedureToTickerList(cTickers,'_adSmooth_score')
	finDF=pd.concat([finDF, ADScores], axis=1)
	aggScore = aggScore + ADScores.mul(0.5).values	
	print('added ad to agg')
	ADScores=[]

	betaScores=dataDict[inpGrp][1][techmetric_betaStr].copy()

	betaScores.iloc[dataDict[inpGrp][1][techmetric_betaStr].values<=0.75]=1
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>0.75) & (dataDict[inpGrp][1][techmetric_betaStr].values<=1.00)]=2
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>1.00) & (dataDict[inpGrp][1][techmetric_betaStr].copy().values<=2.00)]=3
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>2.00) & (dataDict[inpGrp][1][techmetric_betaStr].copy().values<=2.50)]=4
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>2.50)]=5

	betaScores.columns = addProcedureToTickerList(cTickers,'_beta_score')
	finDF=pd.concat([finDF, betaScores], axis=1)
	aggScore = aggScore + betaScores.mul(0.05).values
	betaScores=[]

	volumeScores=dataDict[inpGrp][1][techmetric_volDeltaStr].copy()

	volumeScores.iloc[dataDict[inpGrp][1][techmetric_volDeltaStr].values<=0.75]=1
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>0.75) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=1.00)]=2
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>1.00) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=1.50)]=3
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>1.50) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=2.00)]=4
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>2.00)]=5

	volumeScores.columns = addProcedureToTickerList(cTickers,'_vd_score')
	print('past vol to agg')
	finDF=pd.concat([finDF, volumeScores], axis=1)
	aggScore = aggScore + volumeScores.mul(0.05).values
	
	volumeScores=[]
	print('about to df agg')
	tScores=pd.DataFrame(aggScore)
	print('about to index')
	tScores=tScores.set_index(dataDict[inpGrp][1].index)
	tScores.columns=aggStrings
	print('did col')
	print('going to concat')
	finDF=pd.concat([finDF, tScores], axis=1)
	aggScore=[]
	tScores=[]
	finDF.fillna(method='ffill')
	finDF.fillna(method='bfill')
	return finDF

def discountTechMetrics(dataDict,inputGroup,binWidth):
	# this will produce a transformed version of the df

	cTickers = dataDict[inputGroup][0]
	macroTickers = dataDict['macroDefault'][0]
	macroData = dataDict['macroDefault'][1].loc[dataDict[inputGroup][1].index]

	macroData = dataDict['macroDefault'][1]
	

	dataDict[inputGroup][1] = dataDict[inputGroup][1].loc[macroData.index]



	useETF=0
	if inputGroup == 'macroDefault':
		useETF = 1

	
	fgg = addProcedureToTickerList(cTickers,'_aggTech')
	macroPriceStrings = addProcedureToTickerList(cTickers,'_avg')
	

	energyIndustryTickers = []
	commodityIndustryTickers = []
	airlineIndustryTickers = []
	crackSpreadTickers = [] #14

	if useETF == 0:	
		# uso penalty: penalize if USO is >$100
		thr_uso_1=100
		thr_uso_2=125
		penalty_uso = -0.1
		eligibleTickers = list(set(cTickers).difference(set(energyIndustryTickers)))
		scaleStrings = addProcedureToTickerList(eligibleTickers,'_aggTech')
		dataDict[inputGroup][1][scaleStrings].iloc[(macroData['USO_avg'].values>=thr_uso_1)].add(penalty_uso)
		print('applied USO')

	
		uupScale = macroData['UUP_pp'].mul(100).div(20).mul(-1)
		dataDict[inputGroup][1][scaleStrings].add(uupScale)
		print('applied UUP')

	
		tltScale = macroData['TLT_pp'].div(-20)
		dataDict[inputGroup][1][scaleStrings].add(tltScale)
		print('applied TLT')


	return dataDict[inputGroup][1]

### UI Functions ###

def plotLineSingle(dataDict, selGroup, selTicker, proc, useDate=0, smooth=0):
	plotData = dataDict[selGroup][1]['{}{}'.format(selTicker,proc)]
	if useDate == 1:
		sFig = go.Figure()
		sFig.add_trace(go.Scatter(x=plotData.index,y=plotData.values,mode='lines',name='data'))
		if smooth > 0:
			smthData=plotData.rolling(smooth).mean()
			smthData.iloc[0:smooth-1]=smthData.iloc[smooth]
			sFig.add_trace(go.Scatter(x=plotData.index,y=smthData.values,mode='lines',name='smoothed'))
		sFig.update_layout(autotypenumbers='convert types',xaxis_title="time",yaxis_title='{}{}'.format(selTicker,proc),
			legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
		# sFig = px.line(x=plotData.index, y=plotData.values)

	else:
		sFig = go.Figure()
		sFig.add_trace(go.Scatter(y=plotData.values,mode='lines',name='data'))
		if smooth > 0:
			smthData=plotData.rolling(smooth).mean()
			smthData.iloc[0:smooth-1]=smthData.iloc[smooth]
			sFig.add_trace(go.Scatter(y=smthData.values,mode='lines',name='smoothed'))
		sFig.update_layout(autotypenumbers='convert types',xaxis_title="samples",yaxis_title='{}{}'.format(selTicker,proc),
			legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))


	return sFig


def makeListDict(list,label='a'):
	listDict= pd.DataFrame({label : list})
	return listDict

defaultGroup = ['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT']
defaultTypes = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']
defaultIndustryID = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']

tickers = ['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT']
groups = ['macroDefault']
groupDicts = {}
groupDicts.update({'macroDefault':[defaultGroup,[],defaultTypes]})

totalData = []
haveData = 0
haveAPI = 0
myAPI = ''




initGraph1 = 0
lastPlot1=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])

lastPlot2=px.line(y=[])
initGraph2 = 0

lastPlot3=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])
initGraph3 = 0

lastPlot4=px.line(y=[])
initGraph4 = 0

############################
####	Webapp Layout	####
############################

controls = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("enter api key",key='l1'),
				dbc.Input(id="api-entry", placeholder='', type="text",key='t1',size='sm'),
				dbc.Label("name group"),
				dbc.InputGroup(
					[
						dbc.Input(id="groupAdd-entry", placeholder='', type="text",key='t4',size='sm'),
						dbc.Button("Add", id="groupAdd-button", className="me-2", n_clicks=0,key='b1',size='sm'),
					]),
				
				# html.Div(id='ticker-selector-container'),
				dbc.Label("select group"),
				dcc.Dropdown(id="group-selector",options=[{'label': x, 'value': x} for x in groups]),
				dbc.Label("current group tickers"),
				dcc.Dropdown(id="ticker-selector",options=[{'label': x, 'value': x} for x in tickers]),
				dbc.Button("Remove Ticker", id="removeSelected-button", className="me-2", n_clicks=0,key='b2',size='sm'),
				dbc.Label("grab tickers from SL portfolio"),
				dbc.InputGroup(
					[
						dbc.Input(id="portfolio-entry", placeholder="number", type="int",key='t2',size='sm'),
						dbc.Button("Get Port", id="portfolioAdd-button", className="me-1", n_clicks=0,key='b3',size='sm'),
					]),
				dbc.InputGroup(
					[
						dbc.Input(id="tickerAdd-entry", placeholder='', type="text",key='t3',size='sm'),
						dbc.Button("Add Single", id="tickerAdd-button", className="me-2", n_clicks=0,key='b4',size='sm'),
					]),
			]
		),		
	],
	body=True,)

controlsB = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Get/Score Group's Data"),
				dbc.Button("Get Month Data", id="getData-button", className="me-2", n_clicks=0,key='b5',size='sm'),
				dbc.InputGroup(
					[
						dbc.Button("Get Tech", id="comp_techMet_btn", className="me-2", n_clicks=0,key='b14',size='sm'),
						dbc.Button("Score Tech", id="score_techMet_btn", className="me-2", n_clicks=0,key='b15',size='sm'),
					]),
				html.Div(id='data-shape-container'),
			]
		),		
	],
	body=True,)

controls2 = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Graph To Row 1"),
				html.Br(),
				dbc.Button("Cor Mat", id="plotMat-button", className="me-2", n_clicks=0,key='b6',size='sm'),
				dbc.Button("Grp Avg", id="plotAvg-button", className="me-2", n_clicks=0,key='b13',size='sm'),
				dbc.InputGroup(
					[
						# plot_ticker_price_btn,plot_ticker_volume_btn,plot_ticker_ad_btn,plot_ticker_beta_btn
						# plot_ticker_priceDelta_btn, plot_ticker_volumeDelta_btn, plot_ticker_rsi_btn, plot_ticker_aggTech_btn
						#plot_ticker_ppTech_btn
						dbc.Button("Price", id="plot_ticker_price_btn", className="me-2", n_clicks=0,key='b7',size='sm'),
						dbc.Button("Volume", id="plot_ticker_volume_btn", className="me-2", n_clicks=0,key='b8',size='sm'),
						dbc.Button("Acc Dist", id="plot_ticker_ad_btn", className="me-2", n_clicks=0,key='b9',size='sm'),
						dbc.Button("Beta", id="plot_ticker_beta_btn", className="me-2", n_clicks=0,key='b10',size='sm'),
						dbc.Button("Price Change", id="plot_ticker_priceDelta_btn", className="me-2", n_clicks=0,key='b11',size='sm'),
						dbc.Button("Volume Change", id="plot_ticker_volumeDelta_btn", className="me-2", n_clicks=0,key='b12',size='sm'),
						dbc.Button("RSI", id="plot_ticker_rsi_btn", className="me-2", n_clicks=0,key='b13',size='sm'),
						dbc.Button("aggTech", id="plot_ticker_aggTech_btn", className="me-2", n_clicks=0,key='b19',size='sm'),
						dbc.Button("tech_pp", id="plot_ticker_ppTech_btn", className="me-2", n_clicks=0,key='b20',size='sm'),
						dbc.Button("tech_vd", id="plot_ticker_vdTech_btn", className="me-2", n_clicks=0,key='b21',size='sm'),
						dbc.Button("tech_ad", id="plot_ticker_adTech_btn", className="me-2", n_clicks=0,key='b22',size='sm'),
						dbc.Button("tech_rsi", id="plot_ticker_rsiTech_btn", className="me-2", n_clicks=0,key='b23',size='sm'),
						dbc.Button("tech_beta", id="plot_ticker_betaTech_btn", className="me-2", n_clicks=0,key='b24',size='sm'),


						
		            ]),
				dbc.RadioButton(id="dateOrValues_switch",label="x-axis date",value=False),
				dbc.InputGroup(
					[
						dbc.RadioButton(id="plotSmooth_switch",label="smooth:   ",value=False),
						dbc.Input(id="smooth_entry", placeholder="20", value = 20, type="number",key='t20',size='sm',min=1,inputmode="numeric"),
					]),
				html.Br(),


			]
		),		
	],
	body=True,)

controls3 = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Graph To Row 2"),
				html.Br(),
				dbc.Button("Cor Mat", id="plotMat_button2", className="me-2", n_clicks=0,key='b36',size='sm'),
				dbc.Button("Grp Avg", id="plotAvg-button2", className="me-2", n_clicks=0,key='b313',size='sm'),
				dbc.InputGroup(
					[
						# plot_ticker_price_btn,plot_ticker_volume_btn,plot_ticker_ad_btn,plot_ticker_beta_btn
						# plot_ticker_priceDelta_btn, plot_ticker_volumeDelta_btn, plot_ticker_rsi_btn, plot_ticker_aggTech_btn
						#plot_ticker_ppTech_btn
						dbc.Button("Price", id="plot_ticker_price_btn2", className="me-2", n_clicks=0,key='b2227',size='sm'),
						dbc.Button("Volume", id="plot_ticker_volume_btn2", className="me-2", n_clicks=0,key='b28',size='sm'),
						dbc.Button("Acc Dist", id="plot_ticker_ad_btn2", className="me-2", n_clicks=0,key='b2229',size='sm'),
						dbc.Button("Beta", id="plot_ticker_beta_btn2", className="me-2", n_clicks=0,key='b210',size='sm'),
						dbc.Button("Price Change", id="plot_ticker_priceDelta_btn2", className="me-2", n_clicks=0,key='b211',size='sm'),
						dbc.Button("Volume Change", id="plot_ticker_volumeDelta_btn2", className="me-2", n_clicks=0,key='b212',size='sm'),
						dbc.Button("RSI", id="plot_ticker_rsi_btn2", className="me-2", n_clicks=0,key='b13',size='sm'),
						dbc.Button("aggTech", id="plot_ticker_aggTech_btn2", className="me-2", n_clicks=0,key='b219',size='sm'),
						dbc.Button("tech_pp", id="plot_ticker_ppTech_btn2", className="me-2", n_clicks=0,key='b220',size='sm'),
						dbc.Button("tech_vd", id="plot_ticker_vdTech_btn2", className="me-2", n_clicks=0,key='b221',size='sm'),
						dbc.Button("tech_ad", id="plot_ticker_adTech_btn2", className="me-2", n_clicks=0,key='b222',size='sm'),
						dbc.Button("tech_rsi", id="plot_ticker_rsiTech_btn2", className="me-2", n_clicks=0,key='b223',size='sm'),
						dbc.Button("tech_beta", id="plot_ticker_betaTech_btn2", className="me-2", n_clicks=0,key='b224',size='sm'),


						
		            ]),
				dbc.RadioButton(id="dateOrValues_switch2",label="x-axis date",value=False),
				dbc.InputGroup(
					[
						dbc.RadioButton(id="plotSmooth_switch2",label="smooth:   ",value=False),
						dbc.Input(id="smooth_entry2", placeholder="20", value = 20, type="number",key='t22220',size='sm',min=1,inputmode="numeric"),
					]),
				html.Br(),

			]
		),		
	],
	body=True,)

app.layout = dbc.Container(
	[
		html.H1("SL AI Development"),
		html.Hr(),
		dbc.Row(
			[
				dbc.Col(controls, md=2),
				dbc.Col(controls2, md=2),
				dbc.Col(dcc.Graph(id="plot2-graph"), md=4),
				dbc.Col(dcc.Graph(id="plotM1-graph"), md=3),
			],
			align="top",
		),
		html.Br(),
		dbc.Row(
			[
				dbc.Col(controlsB, md=2),
				dbc.Col(controls3, md=2),
				dbc.Col(dcc.Graph(id="plot3-graph"), md=4),
				dbc.Col(dcc.Graph(id="plotM2-graph"), md=3),
			],
			align="top",
		),
	],
	fluid=True,
)

#comp_techMet_btn
@app.callback(Output("comp_techMet_btn","n_clicks"),
	Input("comp_techMet_btn", "n_clicks"),
	Input('group-selector','value'))
def getGroupTechMetrics(tmBtnClick,selGroup):
	global groupDicts
	if tmBtnClick==1:
		# todo: make bin variable by user
		techMetricData = calculateTechMetrics(groupDicts,selGroup,10)
		groupDicts[selGroup][1]=pd.concat([groupDicts[selGroup][1], techMetricData], axis=1)


	tmBtnClick=0
	return tmBtnClick
	
#score_techMet_btn
@app.callback(Output("score_techMet_btn","n_clicks"),
	Input("score_techMet_btn", "n_clicks"),
	Input('group-selector','value'))
def getGroupTechScores(tmBtnClick,selGroup):

	global groupDicts
	if tmBtnClick==1:
		# todo: make bin variable by user
		try:
			techScoreData = scoreTechMetrics(groupDicts,selGroup,10)
			groupDicts[selGroup][1]=pd.concat([groupDicts[selGroup][1], techScoreData], axis=1)
			try:
				groupDicts[selGroup][1]=discountTechMetrics(groupDicts,selGroup,10)
			except:
				print('problem discounting')
		except:
			print('error with scoring')


	tmBtnClick=0
	return tmBtnClick

@app.callback(Output("plotMat-button","n_clicks"),
	Output("plotM1-graph", "figure"),
	Input("plotMat-button","n_clicks"),
	Input('group-selector','value'))
def make_corMat(mpN,curGroup):
	global lastPlot1

	if mpN == 1:
		try:
			cTickers = groupDicts[curGroup][0]
			procList=addProcedureToTickerList(cTickers,'_avg')
			mfig = px.imshow(groupDicts[curGroup][1][procList].corr())
			lastPlot1=mfig
		except:
			mfig = lastPlot1
	else:
		mfig = lastPlot1

	mpN=0
	lastPlot1 = mfig
	return mpN,mfig

@app.callback(Output("plotMat_button2","n_clicks"),
	Output("plotM2-graph", "figure"),
	Input("plotMat_button2","n_clicks"),
	Input('group-selector','value'))
def make_corMat2(mpN,curGroup):
	global lastPlot3
	if mpN == 1:
		try:
			cTickers = groupDicts[curGroup][0]
			procList=addProcedureToTickerList(cTickers,'_avg')
			mfig = px.imshow(groupDicts[curGroup][1][procList].corr())
			lastPlot3=mfig
		except:
			mfig = lastPlot3
	else:
		mfig = lastPlot3

	mpN=0
	lastPlot3 = mfig
	return mpN,mfig

@app.callback(Output("plot2-graph", "figure"),
	Output("plot_ticker_price_btn","n_clicks"),
	Output("plot_ticker_volume_btn","n_clicks"),
	Output("plot_ticker_ad_btn","n_clicks"),
	Output("plot_ticker_beta_btn","n_clicks"),
	Output("plot_ticker_priceDelta_btn","n_clicks"),
	Output("plot_ticker_volumeDelta_btn","n_clicks"),
	Output("plot_ticker_rsi_btn","n_clicks"),
	Output("plotAvg-button","n_clicks"),
	Output("plot_ticker_aggTech_btn","n_clicks"),
	Output("plot_ticker_ppTech_btn","n_clicks"),
	Output("plot_ticker_vdTech_btn","n_clicks"),
	Output("plot_ticker_adTech_btn","n_clicks"),
	Output("plot_ticker_rsiTech_btn","n_clicks"),
	Output("plot_ticker_betaTech_btn","n_clicks"),

	
	
	Input("plot_ticker_price_btn","n_clicks"),
	Input("plot_ticker_volume_btn","n_clicks"),
	Input("plot_ticker_ad_btn","n_clicks"),
	Input("plot_ticker_beta_btn","n_clicks"),
	Input("plot_ticker_priceDelta_btn","n_clicks"),
	Input("plot_ticker_volumeDelta_btn","n_clicks"),
	Input("plot_ticker_rsi_btn","n_clicks"),
	Input("plotAvg-button","n_clicks"),
	Input("plot_ticker_aggTech_btn","n_clicks"),
	Input("plot_ticker_ppTech_btn","n_clicks"),

	Input("plot_ticker_vdTech_btn","n_clicks"),
	Input("plot_ticker_adTech_btn","n_clicks"),
	Input("plot_ticker_rsiTech_btn","n_clicks"),
	Input("plot_ticker_betaTech_btn","n_clicks"),

	Input('dateOrValues_switch','value'),
	Input('plotSmooth_switch','value'),
	Input('smooth_entry','value'),
	Input('ticker-selector','value'),
	Input('group-selector','value'))
def plot_tickerValues(bT_p,bT_v,bT_ad,bT_b,bT_pd,bT_vd,bT_rsi,aBT,bT_aggT,bT_ppT,bT_vdT,bT_adT,bT_rsiT,bT_betaT,plotWDate,plotWSmooth,smoothBin,curTicker,curGroup):
	global groupDicts
	global lastPlot2
	
	
	if plotWSmooth ==0:
		smoothBin = 0
	
	bStates = ['bT_p','bT_v','bT_ad','bT_b','bT_pd','bT_vd','bT_rsi','aBT','bT_aggT','bT_ppT','bT_vdT','bT_adT','bT_rsiT','bT_betaT']
	try:
		if bT_p==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_avg', useDate=plotWDate,smooth=smoothBin)
		elif bT_v==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_volume', useDate=plotWDate,smooth=smoothBin)
		elif bT_ad==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_adSmooth', useDate=plotWDate,smooth=smoothBin)
		elif bT_b==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_beta', useDate=plotWDate,smooth=smoothBin)
		elif bT_pd==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_pp', useDate=plotWDate,smooth=smoothBin)
		elif bT_vd==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_vd', useDate=plotWDate,smooth=smoothBin)
		elif bT_rsi==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_rsiSmooth', useDate=plotWDate,smooth=smoothBin)
		elif bT_aggT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_aggTech', useDate=plotWDate,smooth=smoothBin)
		elif bT_ppT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_pp_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_vdT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_vd_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_adT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_adSmooth_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_rsiT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_rsiSmooth_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_betaT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_beta_score', useDate=plotWDate,smooth=smoothBin)	
		elif aBT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_avg', useDate=plotWDate,smooth=smoothBin)
		else:
			mfig = lastPlot2
	except:
		mfig = lastPlot2
	bT_p=0
	bT_v=0
	bT_ad=0
	bT_b=0
	bT_pd=0
	bT_vd=0
	bT_rsi=0
	aBT=0
	bT_aggT=0
	bT_ppT=0
	bT_vdT=0
	bT_adT=0
	bT_rsiT=0
	bT_betaT=0
	lastPlot2 = mfig
	return mfig,bT_p,bT_v,bT_ad,bT_b,bT_pd,bT_vd,bT_rsi,aBT,bT_aggT,bT_ppT,bT_vdT,bT_adT,bT_rsiT,bT_betaT

@app.callback(Output("plot3-graph", "figure"),
	Output("plot_ticker_price_btn2","n_clicks"),
	Output("plot_ticker_volume_btn2","n_clicks"),
	Output("plot_ticker_ad_btn2","n_clicks"),
	Output("plot_ticker_beta_btn2","n_clicks"),
	Output("plot_ticker_priceDelta_btn2","n_clicks"),
	Output("plot_ticker_volumeDelta_btn2","n_clicks"),
	Output("plot_ticker_rsi_btn2","n_clicks"),
	Output("plotAvg-button2","n_clicks"),
	Output("plot_ticker_aggTech_btn2","n_clicks"),
	Output("plot_ticker_ppTech_btn2","n_clicks"),
	Output("plot_ticker_vdTech_btn2","n_clicks"),
	Output("plot_ticker_adTech_btn2","n_clicks"),
	Output("plot_ticker_rsiTech_btn2","n_clicks"),
	Output("plot_ticker_betaTech_btn2","n_clicks"),

	
	
	Input("plot_ticker_price_btn2","n_clicks"),
	Input("plot_ticker_volume_btn2","n_clicks"),
	Input("plot_ticker_ad_btn2","n_clicks"),
	Input("plot_ticker_beta_btn2","n_clicks"),
	Input("plot_ticker_priceDelta_btn2","n_clicks"),
	Input("plot_ticker_volumeDelta_btn2","n_clicks"),
	Input("plot_ticker_rsi_btn2","n_clicks"),
	Input("plotAvg-button2","n_clicks"),
	Input("plot_ticker_aggTech_btn2","n_clicks"),
	Input("plot_ticker_ppTech_btn2","n_clicks"),

	Input("plot_ticker_vdTech_btn2","n_clicks"),
	Input("plot_ticker_adTech_btn2","n_clicks"),
	Input("plot_ticker_rsiTech_btn2","n_clicks"),
	Input("plot_ticker_betaTech_btn2","n_clicks"),

	Input('dateOrValues_switch2','value'),
	Input('plotSmooth_switch2','value'),
	Input('smooth_entry2','value'),
	Input('ticker-selector','value'),
	Input('group-selector','value'))
def plot_tickerValues2(bT_p,bT_v,bT_ad,bT_b,bT_pd,bT_vd,bT_rsi,aBT,bT_aggT,bT_ppT,bT_vdT,bT_adT,bT_rsiT,bT_betaT,plotWDate,plotWSmooth,smoothBin,curTicker,curGroup):
	global groupDicts
	global lastPlot4
	if plotWSmooth ==0:
		smoothBin = 0
	
	bStates = ['bT_p','bT_v','bT_ad','bT_b','bT_pd','bT_vd','bT_rsi','aBT','bT_aggT','bT_ppT','bT_vdT','bT_adT','bT_rsiT','bT_betaT']
	try:
		if bT_p==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_avg', useDate=plotWDate,smooth=smoothBin)
		elif bT_v==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_volume', useDate=plotWDate,smooth=smoothBin)
		elif bT_ad==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_adSmooth', useDate=plotWDate,smooth=smoothBin)
		elif bT_b==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_beta', useDate=plotWDate,smooth=smoothBin)
		elif bT_pd==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_pp', useDate=plotWDate,smooth=smoothBin)
		elif bT_vd==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_vd', useDate=plotWDate,smooth=smoothBin)
		elif bT_rsi==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_rsiSmooth', useDate=plotWDate,smooth=smoothBin)
		elif bT_aggT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_aggTech', useDate=plotWDate,smooth=smoothBin)
		elif bT_ppT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_pp_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_vdT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_vd_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_adT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_adSmooth_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_rsiT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_rsiSmooth_score', useDate=plotWDate,smooth=smoothBin)
		elif bT_betaT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_beta_score', useDate=plotWDate,smooth=smoothBin)	
		elif aBT==1:
			mfig = plotLineSingle(groupDicts, curGroup, curTicker, proc = '_avg', useDate=plotWDate,smooth=smoothBin)
		else:
			mfig = lastPlot4
	except:
		mfig = lastPlot4
	bT_p=0
	bT_v=0
	bT_ad=0
	bT_b=0
	bT_pd=0
	bT_vd=0
	bT_rsi=0
	aBT=0
	bT_aggT=0
	bT_ppT=0
	bT_vdT=0
	bT_adT=0
	bT_rsiT=0
	bT_betaT=0
	lastPlot4 = mfig
	return mfig,bT_p,bT_v,bT_ad,bT_b,bT_pd,bT_vd,bT_rsi,aBT,bT_aggT,bT_ppT,bT_vdT,bT_adT,bT_rsiT,bT_betaT

####################################
#### 	Group Entry Callback	####
####################################

@app.callback(Output('group-selector', 'options'),
	Output("groupAdd-button", "n_clicks"),
	Output('group-selector', 'placeholder'),
	Output('group-selector', 'value'),
	Output('groupAdd-entry','value'),
	Input('group-selector', 'value'),
	Input('group-selector', 'placeholder'),
	Input('group-selector', 'options'),
	Input('groupAdd-entry','value'),
	Input("groupAdd-button", "n_clicks"))
def addToGroup_onClick(curValue,curDisp,prevOpts,groupToAdd,gAB):
	global groupDicts
	if gAB == 1:
		if groupToAdd not in list(dict.fromkeys(groupDicts)):
			try:
				print('trying')
				groups = []
				print(groups)
				for i in np.arange(0,len(prevOpts)):
					groups.append(prevOpts[i]['label'])
				groups = groups + [groupToAdd]
				print(groups)
				# dedupe
				groups=list(dict.fromkeys(groups))
				newOptions=[{'label': x, 'value': x} for x in groups]
				groupDicts.update({groupToAdd:[[],[],[]]})
				print('newGroup Dict')
				dispStr=groupToAdd
				entryDispString=''
				curValue=groupToAdd
			except:
				newOptions = prevOpts
				entryDispString=''
				dispStr=curDisp
	else:
		newOptions = prevOpts
		dispStr=curDisp
		entryDispString=groupToAdd
	gAB=0
	return newOptions,gAB,dispStr,curValue,entryDispString


####################################
####	Ticker List Callback	####
####################################

@app.callback(Output('ticker-selector', 'options'),
	Output('tickerAdd-button', "n_clicks"),
	Output("portfolioAdd-button", "n_clicks"),
	Output("removeSelected-button","n_clicks"),


	Input("tickerAdd-button", "n_clicks"),
	Input("portfolioAdd-button", "n_clicks"),
	Input("removeSelected-button", "n_clicks"),
	Input('ticker-selector', 'options'),
	Input('api-entry','value'),
	Input('portfolio-entry','value'),
	Input('tickerAdd-entry','value'),
	Input('ticker-selector', 'value'),
	Input('group-selector', 'value'))
def on_button_click(nTB,nGB,nRB,prevOpts,uAPIKEY,uPort,tickerToAdd,selectedTicker,selectedGroup):
	# state 1: if portfolio add
	global groupDicts
	if nGB == 1:
		print('s1')
		print(selectedGroup)
		try:
			newTickers = getTickersFromPortfolio(uPort,uAPIKEY)
			# see if we have some already, a dict entry may not exist
			try:
				cTickers = groupDicts[selectedGroup][0]
				cTickers = cTickers + newTickers
			except:
				cTickers = newTickers
			print(cTickers)
			print(prevOpts)
			# for i in np.arange(0,len(prevOpts)):
			# 	cTickers.append(prevOpts[i]['label'])
			# dedupe
			cTickers=list(dict.fromkeys(cTickers))
			newOptions=[{'label': x, 'value': x} for x in cTickers]

			print(newOptions)
			try:
				print('isDict?')
				groupDicts[selectedGroup][0]=cTickers
			except:
				print('noDict?')
				groupDicts.update({selectedGroup:[cTickers,[],[]]})
				print('noDict2?')
		except:
			print('error: failed to get new tickers')
			newOptions = prevOpts
	elif nTB == 1:
		print('s2')
		try:
			# see if we have some already
			try:
				cTickers = groupDicts[selectedGroup][0]
			except:
				cTickers = []
			for i in np.arange(0,len(prevOpts)):
				cTickers.append(prevOpts[i]['label'])
			# now add new 
			cTickers = cTickers + [str(tickerToAdd).upper()]
			# dedupe
			cTickers=list(dict.fromkeys(cTickers))
			newOptions=[{'label': x, 'value': x} for x in cTickers]
			try:
				groupDicts[selectedGroup][0]=cTickers
			except:
				groupDicts.update({selectedGroup:[cTickers,[],[]]})

		except:
			print('error: failed to add new ticker')
			newOptions = prevOpts
	elif nRB == 1:
		print('s3')
		try:
			cTickers = []
			for i in np.arange(0,len(prevOpts)):
				if prevOpts[i]['label'] != selectedTicker:
					cTickers.append(prevOpts[i]['label'])
			# now remove new 
			newOptions=[{'label': x, 'value': x} for x in cTickers]
			try:
				groupDicts[selectedGroup][0]=cTickers
			except:
				groupDicts.update({selectedGroup:[cTickers,[],[]]})
		except:
			print('error: failed to remove ticker')
			newOptions = prevOpts
	else:
		try:
			cTickers = groupDicts[selectedGroup][0]
			newOptions=[{'label': x, 'value': x} for x in cTickers]
		except:
			newOptions = prevOpts
	nGB=0
	nTB=0
	nRB=0
	myAPI = uAPIKEY
	return newOptions,nTB,nGB,nRB


###################################
#### Get 1 Month Data Callback ####
###################################

@app.callback(Output('getData-button', "n_clicks"),Output('data-shape-container', 'children'),
	Input('getData-button', "n_clicks"),
	Input('ticker-selector', 'options'),
	Input('api-entry','value'),
	Input('group-selector','value'))
def getOneMonthData(gdB,prevOpts,curAPI,curGroup):
	if gdB==1:
		global totalData
		global groupDicts
		global groups 
		print('console: getting data')
		# todo: check for previous data and don't zero out. 
		totalData=[]
		tickers = []
		for i in np.arange(0,len(prevOpts)):
			tickers.append(prevOpts[i]['label'])
		if len(tickers)>0:
			totalData = getTickerDataFromSL('{}'.format(tickers[0]),curAPI)
			time.sleep(0.2)
			if len(tickers)>1:
				for i in np.arange(1,len(tickers)):
					tempData = getTickerDataFromSL('{}'.format(tickers[i]),curAPI)
					time.sleep(0.2)
					totalData=pd.concat([totalData,tempData], axis=1)
					totalData=totalData.fillna(method='ffill')
		groupDicts.update({curGroup:[tickers,totalData,[]]})
	gdB=0
	print('console: grabbed data')
	return gdB,len(totalData)

###########################
#### The Program Block ####
###########################
# if __name__ == "__main__":
# 	app.run_server(debug=True, port=8888)
if __name__ == '__main__':
    app.run_server(debug=True)